"""When one side crashes, both must stop (per explicit user direction, 2026-10-20):
a failed peer ends every wait on the other side, and a dead app or WinAppDriver ends
the step on its own side instead of waiting out a transfer-length timeout."""

from __future__ import annotations

import pytest
from loguru import logger

from orchestration.statemachine import peer
from orchestration.statemachine.context import RunContext
from orchestration.statemachine.model import Action, Model, State, TextMatch
from orchestration.statemachine.observer import Observation
from orchestration.statemachine.runner import (
    OBSERVE_ERROR_LIMIT_SECONDS,
    PEER_CHECK_SECONDS,
    AppGone,
    PeerFailed,
    Runner,
)
from orchestration.statemachine.scenario import RoleScript, Step


class FakeCoordination:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def wait_for(self, run_id, key, timeout):
        if key not in self.values:
            raise TimeoutError(key)
        return self.values[key]

    def publish(self, run_id, key, value):
        self.values[key] = value


class ScriptedObserver:
    def __init__(self, *queue):
        self.queue = list(queue)
        self.current = self.queue.pop(0)

    def observe(self, session):
        result = self.current
        if self.queue:
            self.current = self.queue.pop(0)
        return result


def obs(screen=None, error=None):
    return Observation(screen=screen, overlay=None, close_prompt=None, error=error)


def ctx(coordination, role="target"):
    return RunContext(role=role, run_id="r", session=None, app=object(), coordination=coordination, log=logger)


def model():
    m = Model(role="t")
    m.add(State("A", "screen", "waiting", text=TextMatch(all=("a",)), next=("B",)))   # A is in transit to B
    m.add(State("B", "screen", "user", text=TextMatch(all=("b",)), actions={"go": Action("go", lambda c, a: None)},
                next=()))
    m.validate()
    return m


def run(observer, context, step_timeout=7200):
    script = RoleScript(role=context.role, steps=[Step(["B"], done=True, expect=["A", "B"])], step_timeout=step_timeout, tick=1.0)
    clock = {"now": 0.0}

    def sleep(s):
        clock["now"] += s

    Runner(model(), script, context, observer, sleep=sleep, clock=lambda: clock["now"]).run()
    return clock["now"]


# ------------------------------------------------------------------ peer failed

def test_peer_failed_is_noticed_while_a_step_waits():
    coordination = FakeCoordination({"source_state": "failed"})
    with pytest.raises(PeerFailed, match="source script reported failed"):
        run(ScriptedObserver(obs("A")), ctx(coordination))


def test_peer_check_is_periodic_not_every_tick():
    coordination = FakeCoordination({"source_state": "migrating"})
    observer = ScriptedObserver(obs("A"))
    context = ctx(coordination)
    script = RoleScript(role="target", steps=[Step(["B"], done=True, expect=["A", "B"])], step_timeout=PEER_CHECK_SECONDS * 3, tick=1.0)
    clock = {"now": 0.0}
    reads = {"n": 0}
    original = coordination.wait_for

    def counting(run_id, key, timeout):
        reads["n"] += 1
        if clock["now"] >= PEER_CHECK_SECONDS * 2:
            coordination.values["source_state"] = "failed"
        return original(run_id, key, timeout)

    coordination.wait_for = counting

    def sleep(s):
        clock["now"] += s

    with pytest.raises(PeerFailed):
        Runner(model(), script, context, observer, sleep=sleep, clock=lambda: clock["now"]).run()
    assert reads["n"] <= 4   # one check per PEER_CHECK_SECONDS, not one per tick


def test_stale_failed_from_an_earlier_run_is_ignored_until_the_peer_publishes():
    coordination = FakeCoordination({"source_state": "failed"})
    context = ctx(coordination)
    peer.snapshot_stale_value(context, "source_state")
    assert not peer.peer_failed(context)
    coordination.values["source_state"] = "started"
    assert not peer.peer_failed(context)
    coordination.values["source_state"] = "failed"
    assert peer.peer_failed(context)


def test_wait_for_state_value_ends_when_the_peer_fails(monkeypatch):
    monkeypatch.setattr(peer.time, "sleep", lambda s: None)
    coordination = FakeCoordination({"target_state": "failed"})
    with pytest.raises(peer.PeerFailed):
        peer.wait_for_state_value(ctx(coordination, role="source"), "target_outcome", ["partial", "clean"], timeout=30)


def test_waiting_for_the_peer_state_itself_accepts_failed():
    coordination = FakeCoordination({"target_state": "failed"})
    assert peer.wait_for_state_value(ctx(coordination, role="source"), "target_state", ["finished", "failed"],
                                     timeout=5) == "failed"


# ------------------------------------------------------------------ app gone

def test_unobservable_app_fails_after_the_limit_not_the_step_timeout():
    coordination = FakeCoordination({"source_state": "migrating"})
    with pytest.raises(AppGone, match="could not observe the app") as exc:
        run(ScriptedObserver(obs(error="/source 500")), ctx(coordination))
    assert "7200" not in str(exc.value)


def test_unobservable_time_is_bounded(monkeypatch):
    coordination = FakeCoordination({"source_state": "migrating"})
    observer = ScriptedObserver(obs(error="/source 500"))
    context = ctx(coordination)
    script = RoleScript(role="target", steps=[Step(["B"], done=True, expect=["A", "B"])], step_timeout=7200, tick=1.0)
    clock = {"now": 0.0}

    def sleep(s):
        clock["now"] += s

    with pytest.raises(AppGone):
        Runner(model(), script, context, observer, sleep=sleep, clock=lambda: clock["now"]).run()
    assert clock["now"] <= OBSERVE_ERROR_LIMIT_SECONDS + 2


def test_exited_process_fails_the_step_at_once(monkeypatch):
    import orchestration.statemachine.runner as runner_module
    monkeypatch.setattr(runner_module, "process_exists", lambda name: False)
    coordination = FakeCoordination({"source_state": "migrating"})
    context = ctx(coordination)
    context.scratch["app_process_name"] = "MyDellExperience"
    with pytest.raises(AppGone, match="process has exited"):
        run(ScriptedObserver(obs(error="connection refused")), context)


def test_a_passing_observation_resets_the_unobservable_clock():
    coordination = FakeCoordination({"source_state": "migrating"})
    flaky = [obs(error="500")] * 30 + [obs("A")] + [obs(error="500")] * 30 + [obs("B")]
    elapsed = run(ScriptedObserver(*flaky), ctx(coordination))
    assert elapsed >= 60   # two 30 s blackouts separated by a good read never add up to the limit
