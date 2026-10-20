"""Step groups (`when:` + `steps:`): parsed flat, branched on a coordination value that
either role may have published, skipped as a whole when the condition does not hold.
full_transfer's second migration after a partial outcome is built on this."""

from __future__ import annotations

import pytest
from loguru import logger

from orchestration import scenario_runner
from orchestration.statemachine import peer
from orchestration.statemachine.context import RunContext
from orchestration.statemachine.model import Action, Model, State, TextMatch
from orchestration.statemachine.observer import Observation
from orchestration.statemachine.runner import Runner, RunnerError
from orchestration.statemachine.scenario import (
    RoleScript,
    ScenarioError,
    Step,
    parse_scenario,
)


class FakeCoordination:
    def __init__(self, values=None):
        self.values = dict(values or {})
        self.published = []

    def wait_for(self, run_id, key, timeout):
        if key not in self.values:
            raise TimeoutError(key)
        return self.values[key]

    def publish(self, run_id, key, value):
        self.values[key] = value
        self.published.append((key, value))


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


def obs(screen):
    return Observation(screen=screen, overlay=None, close_prompt=None)


def scenario(steps):
    return parse_scenario({"name": "t", "roles": {"target": {"steps": steps}}})


# ------------------------------------------------------------------ parsing

def test_groups_are_flattened_in_document_order():
    script = scenario([
        {"at": "A"},
        {"when": {"key": "k", "is": "yes", "among": ["yes", "no"]}, "note": "second round",
         "steps": [{"at": "B", "do": "go"}, {"at": "C"}]},
        {"at": "D", "done": True},
    ]).role("target")
    assert [s.at for s in script.steps] == [["A"], ["B"], ["C"], ["D"]]
    assert [s.index for s in script.steps] == [0, 1, 2, 3]
    assert [s.group for s in script.steps] == [None, "second round", "second round", None]
    assert script.steps[1].when == {"key": "k", "is": "yes", "among": ["yes", "no"], "timeout": 600.0}
    assert "[second round]" in script.steps[1].label()


@pytest.mark.parametrize("group,message", [
    ({"steps": [{"at": "B"}]}, "needs a 'when'"),
    ({"when": {"key": "k", "is": "yes", "among": ["no"]}, "steps": [{"at": "B"}]}, "must be one of"),
    ({"when": {"key": "k"}, "steps": [{"at": "B"}]}, "needs 'key' and 'is'"),
    ({"when": {"key": "k", "is": "yes"}, "steps": []}, "non-empty"),
    ({"when": {"key": "k", "is": "yes"}, "steps": [{"at": "B"}], "at": "X"}, "unknown keys"),
    ({"when": {"key": "k", "is": "yes"},
      "steps": [{"when": {"key": "k", "is": "yes"}, "steps": [{"at": "B"}]}]}, "nested"),
])
def test_group_validation(group, message):
    with pytest.raises(ScenarioError, match=message):
        scenario([{"at": "A"}, group])


# ------------------------------------------------------------------ runner

def make_model(observer, performed):
    def act(name, *push):
        def _perform(ctx, args):
            performed.append(name)
            observer.push(*push)
        return _perform

    m = Model(role="test")
    m.add(State("A", "screen", "user", text=TextMatch(all=("a",)),
                actions={"go": Action("go", act("go", obs("B")), expect=("B",))}, next=()))
    m.add(State("B", "screen", "user", text=TextMatch(all=("b",)),
                actions={"finish": Action("finish", act("finish", obs("A")), expect=("A",))}, next=()))
    m.validate()
    return m


def run_with(coordination, condition_is="partial"):
    observer = ScriptedObserver(obs("A"))
    performed = []
    model = make_model(observer, performed)
    steps = [
        Step(["A"], do="go"),
        Step(["B"], do="finish", when={"key": "outcome", "is": condition_is, "among": ["partial", "clean"], "timeout": 5},
             group="round 2", index=1),
        Step(["A", "B"], done=True, index=2),
    ]
    script = RoleScript(role="target", steps=steps, step_timeout=30, tick=1.0)
    ctx = RunContext(role="target", run_id="r", session=None, app=object(), coordination=coordination, log=logger)
    clock = {"now": 0.0}

    def sleep(s):
        clock["now"] += s

    Runner(model, script, ctx, observer, sleep=sleep, clock=lambda: clock["now"]).run()
    return performed


def test_group_runs_when_the_value_matches():
    assert run_with(FakeCoordination({"outcome": "partial"})) == ["go", "finish"]


def test_group_is_skipped_when_the_value_is_another_allowed_one():
    assert run_with(FakeCoordination({"outcome": "clean"})) == ["go"]


def test_group_fails_clearly_when_the_value_never_arrives(monkeypatch):
    monkeypatch.setattr(peer.time, "sleep", lambda s: None)
    with pytest.raises(RunnerError, match="outcome never became one of"):
        run_with(FakeCoordination({}))


# ------------------------------------------------------------------ peer helpers

def test_publish_takes_a_custom_key():
    coordination = FakeCoordination()
    ctx = RunContext(role="target", run_id="r", session=None, app=object(), coordination=coordination, log=logger)
    model = Model(role="test")
    model.add(State("A", "screen", "user", text=TextMatch(all=("a",)), next=()))
    peer.attach_peer_actions(model, "target_state", "source_state")
    model.get("A").action("publish").perform(ctx, {"key": "target_outcome", "value": "partial"})
    model.get("A").action("publish").perform(ctx, {"value": "migrating"})
    assert coordination.published == [("target_outcome", "partial"), ("target_state", "migrating")]


def test_stale_custom_value_is_ignored_until_it_changes(monkeypatch):
    monkeypatch.setattr(peer.time, "sleep", lambda s: None)
    coordination = FakeCoordination({"target_outcome": "partial"})
    ctx = RunContext(role="source", run_id="r", session=None, app=object(), coordination=coordination, log=logger)
    peer.snapshot_stale_value(ctx, "target_outcome")   # left over from an earlier run with this id
    with pytest.raises(TimeoutError):
        peer.wait_for_state_value(ctx, "target_outcome", ["partial", "clean"], timeout=0.01)
    coordination.values["target_outcome"] = "clean"
    assert peer.wait_for_state_value(ctx, "target_outcome", ["partial", "clean"], timeout=1) == "clean"


def test_scenario_runner_collects_custom_keys():
    script = scenario([
        {"at": "A", "do": "publish", "args": {"key": "target_outcome", "value": "partial"}},
        {"at": "A", "do": "wait_for_peer", "args": {"key": "source_hint", "state": "x"}},
        {"when": {"key": "target_outcome", "is": "partial"}, "steps": [{"at": "B"}]},
        {"at": "A", "do": "publish", "args": {"value": "migrating"}},
    ]).role("target")
    assert scenario_runner.coordination_keys(script) == ({"target_outcome", "source_hint"}, {"target_outcome"})


def test_a_conditional_groups_steps_do_not_skip_optional_steps_outside_it():
    """Run 651 (2026-10-20): the second-round group had its own `migrating` step, so every
    optional step of the retry round was skipped while the retried transfer ran."""
    observer = ScriptedObserver(obs("A"))
    performed = []
    model = make_model(observer, performed)
    steps = [
        Step(["A"], do="go", index=0),                                   # -> B
        Step(["B"], do="finish", optional=True, index=1),                # must run: A is in the group only
        Step(["A"], do="go", when={"key": "k", "is": "yes", "among": ["yes", "no"], "timeout": 5},
             group="round 2", index=2),
        Step(["B"], done=True, index=3),
    ]
    script = RoleScript(role="target", steps=steps, step_timeout=30, tick=1.0)
    ctx = RunContext(role="target", run_id="r", session=None, app=object(),
                     coordination=FakeCoordination({"k": "no"}), log=logger)
    clock = {"now": 0.0}

    def sleep(s):
        clock["now"] += s

    Runner(model, script, ctx, observer, sleep=sleep, clock=lambda: clock["now"]).run()
    assert performed == ["go", "finish"]
