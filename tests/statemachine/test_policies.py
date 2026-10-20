"""Every policy in scenarios/_common.yaml, exercised against the REAL Target/Source
models: the overlay is raised over a screen while a step waits for that screen, and
the runner must do what the policy says -- click the named action and carry on, wait
for the overlay to clear, or fail with the overlay's name. Actions are stubbed (no
WinAppDriver), so this checks the wiring (policy -> state -> action -> runner), not
the live click."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from loguru import logger

from orchestration.statemachine import source_model, target_model
from orchestration.statemachine.context import RunContext
from orchestration.statemachine.observer import Observation
from orchestration.statemachine.runner import PolicyExhausted, Runner, TerminalState
from orchestration.statemachine.scenario import Policy, RoleScript, Step

COMMON = yaml.safe_load((Path(__file__).resolve().parents[2] / "scenarios" / "_common.yaml").read_text(encoding="utf-8"))
MODELS = {"target": target_model, "source": source_model}
BASE_SCREEN = {"target": "migrating", "source": "migrating"}


def obs(screen=None, overlay=None, prompt=None):
    return Observation(screen=screen, overlay=overlay, close_prompt=prompt)


class ScriptedObserver:
    def __init__(self, *queue):
        self.queue = list(queue)
        self.current = self.queue.pop(0)

    def observe(self, session):
        result = self.current
        if self.queue:
            self.current = self.queue.pop(0)
        return result

    def push(self, *observations):
        self.queue.extend(observations)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def cases():
    for role, sets in COMMON["policy_sets"].items():
        for overlay_id, raw in sets["happy_path"].items():
            yield pytest.param(role, overlay_id, Policy.parse(overlay_id, raw), id=f"{role}:{overlay_id}")


@pytest.mark.parametrize("role,overlay_id,policy", list(cases()))
def test_happy_path_policy_drives_the_runner(role, overlay_id, policy):
    model = MODELS[role].build(None)
    state = model.get(overlay_id)
    assert state.layer in ("overlay", "close_prompt"), f"{overlay_id} is a {state.layer}; policies apply to overlays"
    state.probe = lambda session, timeout=0.1: True   # the runner verifies a dialog's locator before acting: it is there
    screen = BASE_SCREEN[role]
    stacked = obs(screen, overlay_id) if state.layer == "overlay" else obs(screen, None, overlay_id)
    observer = ScriptedObserver(stacked)
    performed = []

    if policy.kind == "click":
        action = state.action(policy.action)        # raises ModelError if the policy names a missing action

        def fake_perform(ctx, args):
            performed.append(policy.action)
            observer.push(obs(screen))               # the click dismisses the overlay
        action.perform = fake_perform
    elif policy.kind == "wait_until_gone":
        observer.push(stacked, stacked, obs(screen))  # clears on its own after a few ticks

    policies = {k: Policy.parse(k, v) for k, v in COMMON["policy_sets"][role]["happy_path"].items()}
    script = RoleScript(role=role, steps=[Step(screen, done=True)], policies=policies, step_timeout=120, tick=1.0)
    clock = FakeClock()
    ctx = RunContext(role=role, run_id="r", session=None, app=object(), coordination=None, log=logger)
    runner = Runner(model, script, ctx, observer, sleep=clock.sleep, clock=clock)

    if policy.kind == "fail":
        with pytest.raises(TerminalState) as exc:
            runner.run()
        assert overlay_id in str(exc.value)
    elif policy.kind == "ignore":
        runner.run()  # the overlay is simply not an obstacle
    else:
        runner.run()
        if policy.kind == "click":
            assert performed == [policy.action]
        assert runner.history[-1].screen == screen and runner.history[-1].overlay is None


@pytest.mark.parametrize("role", ["target", "source"])
def test_every_non_recovering_overlay_has_an_explicit_policy(role):
    """An overlay with no policy falls back to the model: fine for auto-recovering ones,
    but a non-recovering overlay would fail the run silently-by-default -- make that a
    deliberate choice in _common.yaml instead."""
    model = MODELS[role].build(None)
    policies = set(COMMON["policy_sets"][role]["happy_path"])
    missing = sorted(
        s.id for s in model.states.values()
        if s.layer in ("overlay", "close_prompt") and not s.auto_recovers and s.id not in policies
    )
    assert not missing, f"{role}: overlays without a happy_path policy: {missing}"


def test_wait_until_gone_cap_fails_when_the_source_never_comes_back():
    """Confirmed live scenario (2026-10-20): the Source app closed; the Target showed the
    other-PC-offline overlay. With wait_until_gone the run must end with a PolicyExhausted
    naming that overlay, not hang."""
    model = target_model.build(None)
    observer = ScriptedObserver(obs("migrating", "otherPcNoNetwork"))
    policies = {"otherPcNoNetwork": Policy(kind="wait_until_gone", cap=30)}
    script = RoleScript(role="target", steps=[Step("resultsSummary", done=True)], policies=policies,
                        step_timeout=600, tick=5.0)
    clock = FakeClock()
    ctx = RunContext(role="target", run_id="r", session=None, app=object(), coordination=None, log=logger)
    with pytest.raises(PolicyExhausted) as exc:
        Runner(model, script, ctx, observer, sleep=clock.sleep, clock=clock).run()
    assert "otherPcNoNetwork still showing after 30s" in str(exc.value)
