"""Scenario files: YAML in, validated dataclasses out.

Shape (see scenarios/*.yaml):

    name: full_transfer
    description: ...
    launch: exe                      # optional; Target launch mode (exe|mock|simulator)
    roles:
      target:
        defaults: {step_timeout: 300, tick: 0.5}
        setup: [ensure_notepad_closed]          # names resolved by utils/environment.py
        teardown: []
        policies:
          trustNetwork: {click: trust_network}
          noNetwork:    {wait_until_gone: 600}
          failure:      fail
          desktopShortcut: {click: no_thanks, max: 3}
        steps:
          - at: welcome
            do: continue
          - at: enterCode
            do: type_code
            args: {source: coordination}
            timeout: 120
          - at: migrating
            expect: [resultsSummary]
          - at: welcome
            done: true
      source:
        ...

A step with no `do` (or `do: wait`) only waits until `at` is showing. `expect` narrows
the legal next states after the action (defaults to the action's own expect list in the
model). `done: true` ends the role's script once `at` is reached.

Validation happens against the Model BEFORE anything is launched, so a typo fails in a
second rather than twenty minutes into a transfer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from orchestration.statemachine.model import Model

WAIT = "wait"
POLICY_KINDS = ("click", "wait_until_gone", "fail", "ignore")


class ScenarioError(Exception):
    pass


@dataclass
class Step:
    at: str
    do: Optional[str] = None
    args: Dict[str, Any] = field(default_factory=dict)
    expect: Optional[List[str]] = None
    timeout: Optional[float] = None
    done: bool = False
    note: str = ""
    index: int = 0

    @property
    def is_wait(self) -> bool:
        return self.do in (None, WAIT)

    def label(self) -> str:
        what = "wait" if self.is_wait else self.do
        return f"step {self.index + 1} (at {self.at}: {what})"


@dataclass
class Policy:
    kind: str                      # one of POLICY_KINDS
    action: Optional[str] = None   # for click
    cap: Optional[float] = None    # seconds, for wait_until_gone
    max_times: Optional[int] = None  # for click

    @classmethod
    def parse(cls, overlay_id: str, raw: Any) -> "Policy":
        if isinstance(raw, str):
            if raw in ("fail", "ignore"):
                return cls(kind=raw)
            raise ScenarioError(f"policy for {overlay_id!r}: unknown shorthand {raw!r} (use fail|ignore or a mapping)")
        if not isinstance(raw, dict):
            raise ScenarioError(f"policy for {overlay_id!r} must be a string or mapping, got {type(raw).__name__}")
        kinds = [k for k in raw if k in POLICY_KINDS]
        if len(kinds) != 1:
            raise ScenarioError(f"policy for {overlay_id!r} must have exactly one of {POLICY_KINDS}, got {sorted(raw)}")
        kind = kinds[0]
        if kind == "click":
            return cls(kind="click", action=str(raw["click"]), max_times=raw.get("max"))
        if kind == "wait_until_gone":
            cap = raw["wait_until_gone"]
            return cls(kind="wait_until_gone", cap=float(cap) if cap is not None else None)
        return cls(kind=kind)


@dataclass
class RoleScript:
    role: str
    steps: List[Step]
    policies: Dict[str, Policy] = field(default_factory=dict)
    setup: List[str] = field(default_factory=list)
    teardown: List[str] = field(default_factory=list)
    step_timeout: float = 300.0
    tick: float = 0.5


@dataclass
class Scenario:
    name: str
    roles: Dict[str, RoleScript]
    description: str = ""
    launch: Optional[str] = None
    path: Optional[Path] = None

    def role(self, role: str) -> RoleScript:
        try:
            return self.roles[role]
        except KeyError:
            raise ScenarioError(f"Scenario {self.name!r} has no script for role {role!r}") from None


def _parse_step(index: int, raw: Any) -> Step:
    if not isinstance(raw, dict) or "at" not in raw:
        raise ScenarioError(f"step {index + 1} must be a mapping with an 'at' key, got {raw!r}")
    unknown = set(raw) - {"at", "do", "args", "expect", "timeout", "done", "note"}
    if unknown:
        raise ScenarioError(f"step {index + 1}: unknown keys {sorted(unknown)}")
    expect = raw.get("expect")
    if expect is not None and not isinstance(expect, list):
        expect = [expect]
    return Step(
        at=str(raw["at"]),
        do=raw.get("do"),
        args=dict(raw.get("args") or {}),
        expect=[str(e) for e in expect] if expect is not None else None,
        timeout=float(raw["timeout"]) if raw.get("timeout") is not None else None,
        done=bool(raw.get("done", False)),
        note=str(raw.get("note") or ""),
        index=index,
    )


def _parse_role(role: str, raw: Any) -> RoleScript:
    if not isinstance(raw, dict) or not isinstance(raw.get("steps"), list) or not raw["steps"]:
        raise ScenarioError(f"role {role!r} needs a non-empty 'steps' list")
    defaults = raw.get("defaults") or {}
    return RoleScript(
        role=role,
        steps=[_parse_step(i, s) for i, s in enumerate(raw["steps"])],
        policies={str(k): Policy.parse(str(k), v) for k, v in (raw.get("policies") or {}).items()},
        setup=[str(s) for s in (raw.get("setup") or [])],
        teardown=[str(s) for s in (raw.get("teardown") or [])],
        step_timeout=float(defaults.get("step_timeout", 300.0)),
        tick=float(defaults.get("tick", 0.5)),
    )


def parse_scenario(data: Dict[str, Any], path: Optional[Path] = None) -> Scenario:
    if not isinstance(data, dict) or "name" not in data or not isinstance(data.get("roles"), dict):
        raise ScenarioError(f"{path or 'scenario'}: top level needs 'name' and a 'roles' mapping")
    roles = {str(r): _parse_role(str(r), body) for r, body in data["roles"].items()}
    return Scenario(
        name=str(data["name"]),
        description=str(data.get("description") or ""),
        launch=data.get("launch"),
        roles=roles,
        path=path,
    )


def load_scenario(path) -> Scenario:
    path = Path(path)
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return parse_scenario(data, path)


def validate_role_script(script: RoleScript, model: Model) -> List[str]:
    """Returns a list of problems (empty = valid). Checks every state/action/policy name
    against the model so the run fails before launch rather than mid-transfer."""
    problems: List[str] = []
    for step in script.steps:
        if not model.has(step.at):
            problems.append(f"{step.label()}: unknown state {step.at!r}")
            continue
        state = model.get(step.at)
        if not step.is_wait and step.do not in state.actions:
            problems.append(
                f"{step.label()}: state {step.at!r} has no action {step.do!r} (has: {sorted(state.actions) or 'none'})"
            )
        for exp in step.expect or []:
            if not model.has(exp):
                problems.append(f"{step.label()}: expect names unknown state {exp!r}")
    last = script.steps[-1]
    if not last.done:
        problems.append(f"last step must have done: true (got {last.label()})")
    for overlay_id, policy in script.policies.items():
        if not model.has(overlay_id):
            problems.append(f"policy for unknown state {overlay_id!r}")
            continue
        state = model.get(overlay_id)
        if state.layer == "screen":
            problems.append(f"policy for {overlay_id!r}: policies apply to overlays/close prompts, not screens")
        if policy.kind == "click" and policy.action not in state.actions:
            problems.append(
                f"policy for {overlay_id!r}: no action {policy.action!r} (has: {sorted(state.actions) or 'none'})"
            )
    return problems


def validate_scenario(scenario: Scenario, models: Dict[str, Model]) -> None:
    problems: List[str] = []
    for role, script in scenario.roles.items():
        if role not in models:
            problems.append(f"no model for role {role!r}")
            continue
        problems.extend(f"[{role}] {p}" for p in validate_role_script(script, models[role]))
    if problems:
        raise ScenarioError(f"Scenario {scenario.name!r} is invalid:\n  " + "\n  ".join(problems))
