"""Runner/model/scenario unit tests -- no hardware, no WinAppDriver. A ScriptedObserver
plays back observations; fake actions push the next observation, so the runner's own
logic (policies, transit, timeouts, failure messages) is what's under test."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import pytest
from loguru import logger

from orchestration.statemachine.context import RunContext
from orchestration.statemachine.model import Action, Model, ModelError, State, TextMatch, normalize
from orchestration.statemachine.observer import Observation, SnapshotObserver
from orchestration.statemachine.runner import (
    PolicyExhausted,
    Runner,
    StepTimeout,
    TerminalState,
    UnexpectedState,
)
from orchestration.statemachine.scenario import (
    Policy,
    RoleScript,
    ScenarioError,
    Step,
    parse_scenario,
    validate_role_script,
)


# ----------------------------------------------------------------- fixtures / fakes

def obs(screen=None, overlay=None, prompt=None):
    return Observation(screen=screen, overlay=overlay, close_prompt=prompt)


class ScriptedObserver:
    """Returns queued observations in order; repeats the last one forever."""

    def __init__(self, *queue: Observation):
        self.queue: List[Observation] = list(queue)
        self.current = self.queue.pop(0) if self.queue else obs()
        self.ticks = 0

    def observe(self, session):
        self.ticks += 1
        result = self.current
        if self.queue:
            self.current = self.queue.pop(0)
        return result

    def push(self, *observations: Observation):
        self.queue.extend(observations)


@dataclass
class Calls:
    performed: List[str] = field(default_factory=list)


def make_model(calls: Calls, observer: ScriptedObserver) -> Model:
    """A: user screen with action go -> B.  B: waiting -> C.  C: user, action finish -> A.
    X: auto-recovering overlay.  Y: overlay with a dismiss action.  F: terminal overlay."""

    def act(name, *push):
        def _perform(ctx, args):
            calls.performed.append(name + (f"{args}" if args else ""))
            observer.push(*push)
        return _perform

    m = Model(role="test")
    m.add(State("A", "screen", "user", text=TextMatch(all=("screen a",)),
                actions={"go": Action("go", act("A.go", obs("B")), expect=("B",))}))
    m.add(State("B", "screen", "waiting", text=TextMatch(all=("screen b",)), next=("C",)))
    m.add(State("C", "screen", "user", text=TextMatch(all=("screen c",)),
                actions={"finish": Action("finish", act("C.finish", obs("A")), expect=("A",))}))
    m.add(State("D", "screen", "user", text=TextMatch(all=("screen d",))))
    m.add(State("X", "overlay", text=TextMatch(all=("overlay x",)), auto_recovers=True))
    m.add(State("Y", "overlay", text=TextMatch(all=("overlay y",)),
                actions={"dismiss": Action("dismiss", act("Y.dismiss", obs("A")))}))
    m.add(State("F", "overlay", "terminal", text=TextMatch(all=("overlay f",)),
                actions={"read_text": Action("read_text", lambda ctx, a: "error 2468")}))
    m.add(State("P", "close_prompt", text=TextMatch(all=("prompt p",)),
                actions={"no": Action("no", act("P.no", obs("A")))}))
    m.validate()
    return m


def make_ctx():
    return RunContext(role="test", run_id="r1", session=None, app=object(), coordination=None, log=logger)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def run(model, steps, observer, policies=None, step_timeout=30.0):
    script = RoleScript(role="test", steps=steps, policies=policies or {}, step_timeout=step_timeout, tick=1.0)
    clock = FakeClock()
    runner = Runner(model, script, make_ctx(), observer, sleep=clock.sleep, clock=clock)
    runner.run()
    return runner


# ----------------------------------------------------------------- runner behaviour

def test_happy_path_performs_actions_and_waits_through_transit():
    calls, observer = Calls(), ScriptedObserver(obs("A"))
    model = make_model(calls, observer)
    steps = [Step("A", "go", index=0), Step("C", "finish", index=1), Step("A", done=True, index=2)]

    def go(ctx, args):  # A.go lands on B, then the engine moves on to C by itself
        calls.performed.append("A.go")
        observer.push(obs("B"), obs("C"))

    model.get("A").actions["go"].perform = go
    runner = run(model, steps, observer)
    assert calls.performed == ["A.go", "C.finish"]
    assert [o.screen for o in runner.history] == ["A", "B", "C", "A"]


def test_auto_recovering_overlay_is_waited_out_without_a_policy():
    calls, observer = Calls(), ScriptedObserver(obs("A"), obs("A", "X"), obs("A", "X"), obs("A"))
    model = make_model(calls, observer)
    run(model, [Step("A", "go", index=0), Step("B", done=True, index=1)], observer)
    assert calls.performed == ["A.go"]


def test_wait_until_gone_cap_raises_policy_exhausted():
    calls, observer = Calls(), ScriptedObserver(obs("A", "X"))
    model = make_model(calls, observer)
    with pytest.raises(PolicyExhausted) as exc:
        run(model, [Step("A", "go", index=0), Step("B", done=True, index=1)], observer,
            policies={"X": Policy(kind="wait_until_gone", cap=5)})
    assert "X" in str(exc.value) and "overlay=X" in str(exc.value)


def test_click_policy_dismisses_overlay_then_continues():
    calls, observer = Calls(), ScriptedObserver(obs("A", "Y"))
    model = make_model(calls, observer)
    run(model, [Step("A", "go", index=0), Step("B", done=True, index=1)], observer,
        policies={"Y": Policy(kind="click", action="dismiss")})
    assert calls.performed == ["Y.dismiss", "A.go"]


def test_click_policy_max_is_enforced():
    calls, observer = Calls(), ScriptedObserver(obs("A", "Y"))
    model = make_model(calls, observer)
    # dismiss pushes A, but the observer keeps showing Y again each time
    observer.push(obs("A", "Y"), obs("A", "Y"), obs("A", "Y"))
    model.get("Y").actions["dismiss"].perform = lambda ctx, a: calls.performed.append("Y.dismiss")
    with pytest.raises(PolicyExhausted):
        run(model, [Step("A", "go", index=0), Step("B", done=True, index=1)], observer,
            policies={"Y": Policy(kind="click", action="dismiss", max_times=2)})
    assert calls.performed.count("Y.dismiss") == 2


def test_unpoliced_non_recovering_overlay_fails():
    calls, observer = Calls(), ScriptedObserver(obs("A", "Y"))
    model = make_model(calls, observer)
    with pytest.raises(TerminalState) as exc:
        run(model, [Step("A", "go", index=0), Step("B", done=True, index=1)], observer)
    assert "Y appeared (policy: fail)" in str(exc.value)


def test_terminal_overlay_message_includes_read_text():
    calls, observer = Calls(), ScriptedObserver(obs("A", "F"))
    model = make_model(calls, observer)
    with pytest.raises(TerminalState) as exc:
        run(model, [Step("A", "go", index=0), Step("B", done=True, index=1)], observer)
    assert "error 2468" in str(exc.value)


def test_close_prompt_takes_precedence_over_overlay_and_uses_its_policy():
    calls, observer = Calls(), ScriptedObserver(obs("A", "X", "P"))
    model = make_model(calls, observer)
    run(model, [Step("A", "go", index=0), Step("B", done=True, index=1)], observer,
        policies={"P": Policy(kind="click", action="no")})
    assert calls.performed[0] == "P.no"


def test_unexpected_screen_raises_with_location():
    calls, observer = Calls(), ScriptedObserver(obs("A"))
    model = make_model(calls, observer)
    observer.push(obs("D"))  # D is not reachable from A.go's expect (B) nor via next
    with pytest.raises(UnexpectedState) as exc:
        run(model, [Step("A", "go", index=0), Step("C", done=True, index=1)], observer)
    msg = str(exc.value)
    assert "got D" in msg and "screen=D" in msg and "step 2" in msg


def test_step_timeout_carries_last_observation():
    calls, observer = Calls(), ScriptedObserver(obs("A"))
    model = make_model(calls, observer)
    model.get("A").actions["go"].perform = lambda ctx, a: calls.performed.append("A.go")  # never leaves A
    with pytest.raises(StepTimeout) as exc:
        run(model, [Step("A", "go", index=0), Step("B", done=True, index=1)], observer, step_timeout=5)
    assert "B did not appear within 5s" in str(exc.value) and "screen=A" in str(exc.value)


def test_observation_error_is_tolerated_until_timeout():
    calls, observer = Calls(), ScriptedObserver(Observation(None, None, None, error="UAC?"), obs("A"))
    model = make_model(calls, observer)
    runner = run(model, [Step("A", done=True, index=0)], observer)
    assert runner.history[-1].screen == "A"


def test_overlay_step_is_reached_when_that_overlay_shows():
    calls, observer = Calls(), ScriptedObserver(obs("A", "Y"))
    model = make_model(calls, observer)
    run(model, [Step("Y", "dismiss", index=0), Step("A", done=True, index=1)], observer)
    assert calls.performed == ["Y.dismiss"]


def test_action_args_are_passed_through():
    calls, observer = Calls(), ScriptedObserver(obs("A"))
    model = make_model(calls, observer)
    observer.push(obs("B"))
    run(model, [Step("A", "go", args={"n": 1}, index=0), Step("B", done=True, index=1)], observer)
    assert calls.performed == ["A.go{'n': 1}"]


# ----------------------------------------------------------------- model / text matching

def test_normalize_handles_entities_curly_quotes_and_case():
    assert normalize("We&apos;re  Ready’s &amp; Done") == "we're ready's & done"


def test_textmatch_all_any_none():
    tm = TextMatch(all=("alpha",), any=("beta", "gamma"), none=("delta",))
    assert tm.matches("xx alpha yy gamma")
    assert not tm.matches("alpha only")
    assert not tm.matches("alpha beta delta")
    with pytest.raises(ModelError):
        TextMatch()


def test_state_needs_a_detector_and_model_validates_references():
    with pytest.raises(ModelError):
        State("Z", "screen")
    m = Model("r")
    m.add(State("A", "screen", text=TextMatch(all=("a",)), next=("missing",)))
    with pytest.raises(ModelError):
        m.validate()


def test_snapshot_observer_respects_layers_and_priority():
    calls, observer = Calls(), ScriptedObserver()
    model = make_model(calls, observer)
    model.add(State("A2", "screen", text=TextMatch(all=("screen a", "extra")), priority=10))

    class FakeSession:
        page_source = '<Window Name="Screen A"/><Text Name="EXTRA"/><Text Name="Overlay X"/><Text Name="Prompt P"/>'

    o = SnapshotObserver(model).observe(FakeSession())
    assert (o.screen, o.overlay, o.close_prompt) == ("A2", "X", "P")


def test_snapshot_observer_reports_source_errors():
    calls, observer = Calls(), ScriptedObserver()
    model = make_model(calls, observer)

    class Broken:
        @property
        def page_source(self):
            raise RuntimeError("boom")

    o = SnapshotObserver(model).observe(Broken())
    assert o.error and "boom" in o.error and o.screen is None


# ----------------------------------------------------------------- scenario parsing / validation

def test_parse_and_validate_scenario_against_model():
    calls, observer = Calls(), ScriptedObserver()
    model = make_model(calls, observer)
    data = {
        "name": "demo",
        "roles": {"test": {
            "policies": {"X": {"wait_until_gone": 10}, "Y": {"click": "dismiss", "max": 2}, "F": "fail"},
            "steps": [{"at": "A", "do": "go"}, {"at": "C", "do": "finish", "expect": ["A"]}, {"at": "A", "done": True}],
        }},
    }
    scenario = parse_scenario(data)
    assert validate_role_script(scenario.role("test"), model) == []
    assert scenario.role("test").policies["Y"].max_times == 2


def test_validation_reports_every_problem():
    calls, observer = Calls(), ScriptedObserver()
    model = make_model(calls, observer)
    data = {"name": "bad", "roles": {"test": {
        "policies": {"Nope": "fail", "A": "fail", "Y": {"click": "wrong"}},
        "steps": [{"at": "A", "do": "fly"}, {"at": "Q"}, {"at": "C", "expect": ["Zzz"]}],
    }}}
    problems = validate_role_script(parse_scenario(data).role("test"), model)
    joined = "\n".join(problems)
    for needle in ("no action 'fly'", "unknown state 'Q'", "unknown state 'Zzz'", "done: true",
                   "unknown state 'Nope'", "not screens", "no action 'wrong'"):
        assert needle in joined, needle


def test_bad_policy_shapes_are_rejected():
    with pytest.raises(ScenarioError):
        Policy.parse("X", "maybe")
    with pytest.raises(ScenarioError):
        Policy.parse("X", {"click": "a", "fail": None})
    with pytest.raises(ScenarioError):
        parse_scenario({"name": "n", "roles": {"t": {"steps": [{"at": "A", "bogus": 1}]}}})
