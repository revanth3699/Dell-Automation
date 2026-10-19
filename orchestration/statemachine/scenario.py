"""Scenario files: YAML in, validated dataclasses out.

Shape (see scenarios/*.yaml and scenarios/_common.yaml):

    name: full_transfer
    description: ...
    launch: exe                      # optional; Target launch mode (exe|mock|simulator)
    roles:
      target:
        defaults: {step_timeout: 300, tick: 0.5}
        setup: [open_notepad]        # names from utils/environment.py, run before launch
        teardown: [close_notepad]
        policies:
          base: happy_path           # a named set from scenarios/_common.yaml (per role)
          noNetwork: {wait_until_gone: 600}      # overrides / additions
          failure: fail
          desktopShortcut: {click: no_thanks, max: 3}
        steps:
          - at: [welcome, welcomeSignedOut]      # one id or a list: any of them
            do: continue
          - at: signIn
            do: sign_in
            optional: true           # skipped if the NEXT step's target shows up first
            timeout: 600
          - at: migrating
            env: disable_network     # an environment step instead of a model action
          - at: enterCode
            do: type_code
            args: {timeout: 300}
            wait_before: 5           # seconds to pause once the state is showing
          - at: welcome
            done: true

A step with neither `do` nor `env` only waits until `at` is showing. `expect` narrows
the legal next states after the action (defaults to the action's own expect list in
the model). `done: true` ends the role's script once `at` is reached.

Validation happens against the Model BEFORE anything is launched, so a typo fails in a
second rather than twenty minutes into a transfer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from orchestration.statemachine.model import Model
from utils import environment

POLICY_KINDS = ("click", "wait_until_gone", "fail", "ignore")
COMMON_FILE = "_common.yaml"
STEP_KEYS = {"at", "do", "env", "args", "expect", "timeout", "done", "note", "optional", "wait_before"}


class ScenarioError(Exception):
    pass


@dataclass
class Step:
    at: list[str]
    do: str | None = None
    env: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    expect: list[str] | None = None
    timeout: float | None = None
    done: bool = False
    optional: bool = False
    wait_before: float = 0.0
    note: str = ""
    index: int = 0

    def __post_init__(self):
        if isinstance(self.at, str):
            self.at = [self.at]

    @property
    def is_wait(self) -> bool:
        return self.do is None and self.env is None

    def label(self) -> str:
        what = f"env:{self.env}" if self.env else ("wait" if self.is_wait else self.do)
        return f"step {self.index + 1} (at {'/'.join(self.at)}: {what})"


@dataclass
class Policy:
    kind: str                      # one of POLICY_KINDS
    action: str | None = None   # for click
    cap: float | None = None    # seconds, for wait_until_gone
    max_times: int | None = None  # for click

    @classmethod
    def parse(cls, overlay_id: str, raw: Any) -> Policy:
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
    steps: list[Step]
    policies: dict[str, Policy] = field(default_factory=dict)
    setup: list[str] = field(default_factory=list)
    teardown: list[str] = field(default_factory=list)
    step_timeout: float = 300.0
    tick: float = 0.5


@dataclass
class Scenario:
    name: str
    roles: dict[str, RoleScript]
    description: str = ""
    launch: str | None = None
    path: Path | None = None

    def role(self, role: str) -> RoleScript:
        try:
            return self.roles[role]
        except KeyError:
            raise ScenarioError(f"Scenario {self.name!r} has no script for role {role!r}") from None


def _parse_step(index: int, raw: Any) -> Step:
    if not isinstance(raw, dict) or "at" not in raw:
        raise ScenarioError(f"step {index + 1} must be a mapping with an 'at' key, got {raw!r}")
    unknown = set(raw) - STEP_KEYS
    if unknown:
        raise ScenarioError(f"step {index + 1}: unknown keys {sorted(unknown)}")
    if raw.get("do") is not None and raw.get("env") is not None:
        raise ScenarioError(f"step {index + 1}: use either 'do' or 'env', not both")
    at = raw["at"]
    at_list = [str(a) for a in at] if isinstance(at, list) else [str(at)]
    if not at_list:
        raise ScenarioError(f"step {index + 1}: 'at' must name at least one state")
    expect = raw.get("expect")
    if expect is not None and not isinstance(expect, list):
        expect = [expect]
    return Step(
        at=at_list,
        do=str(raw["do"]) if raw.get("do") is not None else None,
        env=str(raw["env"]) if raw.get("env") is not None else None,
        args=dict(raw.get("args") or {}),
        expect=[str(e) for e in expect] if expect is not None else None,
        timeout=float(raw["timeout"]) if raw.get("timeout") is not None else None,
        done=bool(raw.get("done", False)),
        optional=bool(raw.get("optional", False)),
        wait_before=float(raw.get("wait_before") or 0.0),
        note=str(raw.get("note") or ""),
        index=index,
    )


def _resolve_policies(role: str, raw: Any, policy_sets: dict[str, dict[str, Any]]) -> dict[str, Policy]:
    raw = dict(raw or {})
    merged: dict[str, Any] = {}
    base = raw.pop("base", None)
    if base is not None:
        role_sets = policy_sets.get(role) or {}
        if base not in role_sets:
            raise ScenarioError(
                f"role {role!r}: policies base {base!r} not found (known for this role: {sorted(role_sets) or 'none'})"
            )
        merged.update(role_sets[base])
    merged.update(raw)
    return {str(k): Policy.parse(str(k), v) for k, v in merged.items()}


def _parse_role(role: str, raw: Any, policy_sets: dict[str, dict[str, Any]]) -> RoleScript:
    if not isinstance(raw, dict) or not isinstance(raw.get("steps"), list) or not raw["steps"]:
        raise ScenarioError(f"role {role!r} needs a non-empty 'steps' list")
    defaults = raw.get("defaults") or {}
    return RoleScript(
        role=role,
        steps=[_parse_step(i, s) for i, s in enumerate(raw["steps"])],
        policies=_resolve_policies(role, raw.get("policies"), policy_sets),
        setup=[str(s) for s in (raw.get("setup") or [])],
        teardown=[str(s) for s in (raw.get("teardown") or [])],
        step_timeout=float(defaults.get("step_timeout", 300.0)),
        tick=float(defaults.get("tick", 0.5)),
    )


def _load_policy_sets(data: dict[str, Any], path: Path | None) -> dict[str, dict[str, Any]]:
    """Named policy sets: from the file's own `policy_sets`, else from _common.yaml next
    to it."""
    if isinstance(data.get("policy_sets"), dict):
        return data["policy_sets"]
    if path is not None:
        common = Path(path).parent / COMMON_FILE
        if common.exists():
            with common.open("r", encoding="utf-8") as fh:
                common_data = yaml.safe_load(fh) or {}
            if isinstance(common_data.get("policy_sets"), dict):
                return common_data["policy_sets"]
    return {}


def parse_scenario(data: dict[str, Any], path: Path | None = None) -> Scenario:
    if not isinstance(data, dict) or "name" not in data or not isinstance(data.get("roles"), dict):
        raise ScenarioError(f"{path or 'scenario'}: top level needs 'name' and a 'roles' mapping")
    policy_sets = _load_policy_sets(data, path)
    roles = {str(r): _parse_role(str(r), body, policy_sets) for r, body in data["roles"].items()}
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


def validate_role_script(script: RoleScript, model: Model) -> list[str]:
    """Returns a list of problems (empty = valid). Checks every state/action/policy/env
    name against the model so the run fails before launch rather than mid-transfer."""
    problems: list[str] = []
    for step in script.steps:
        for target in step.at:
            if not model.has(target):
                problems.append(f"{step.label()}: unknown state {target!r}")
                continue
            state = model.get(target)
            if step.do is not None and step.do not in state.actions:
                problems.append(
                    f"{step.label()}: state {target!r} has no action {step.do!r} (has: {sorted(state.actions) or 'none'})"
                )
        if step.env is not None and step.env not in environment.STEPS:
            problems.append(f"{step.label()}: unknown environment step {step.env!r} (known: {sorted(environment.STEPS)})")
        for exp in step.expect or []:
            if not model.has(exp):
                problems.append(f"{step.label()}: expect names unknown state {exp!r}")
    last = script.steps[-1]
    if not last.done:
        problems.append(f"last step must have done: true (got {last.label()})")
    if last.optional:
        problems.append("last step cannot be optional")
    for name in script.setup + script.teardown:
        if name not in environment.STEPS:
            problems.append(f"unknown environment step {name!r} in setup/teardown (known: {sorted(environment.STEPS)})")
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


def validate_scenario(scenario: Scenario, models: dict[str, Model]) -> None:
    problems: list[str] = []
    for role, script in scenario.roles.items():
        if role not in models:
            problems.append(f"no model for role {role!r}")
            continue
        problems.extend(f"[{role}] {p}" for p in validate_role_script(script, models[role]))
    if problems:
        raise ScenarioError(f"Scenario {scenario.name!r} is invalid:\n  " + "\n  ".join(problems))
