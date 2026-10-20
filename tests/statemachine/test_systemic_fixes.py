"""One test per systemic fix from the 2026-10-19/20 live runs (see
TARGET_STATE_MACHINE.md Sec 11) -- each guards the ROOT CAUSE, not the instance."""

from __future__ import annotations

import pytest
from loguru import logger

from orchestration.statemachine import peer
from orchestration.statemachine.context import RunContext
from orchestration.statemachine.model import Action, Model, State, TextMatch
from orchestration.statemachine.observer import Observation, SnapshotObserver
from orchestration.statemachine.runner import Runner
from orchestration.statemachine.scenario import RoleScript, Step, lint_role_script

# ---------------------------------------------------------------- RCA 1: substring collisions

def test_snapshot_observer_prefers_the_more_specific_match():
    """A short heading contained in another dialog's body must lose to the state anchored
    on more text, regardless of definition order."""
    m = Model("t")
    m.add(State("shortFirst", "overlay", text=TextMatch(all=("connect to a trusted network",))))
    m.add(State("longer", "overlay", text=TextMatch(all=("it looks like your network has been disconnected",))))
    m.add(State("home", "screen", text=TextMatch(all=("home",))))

    class S:
        page_source = ('<Text Name="home"/><Text Name="It looks like your network has been disconnected"/>'
                       '<Text Name="Reconnect to a trusted network to continue."/>')

    assert SnapshotObserver(m).observe(S()).overlay == "longer"


# ---------------------------------------------------------------- RCA 2: brief engine screens

def test_step_on_a_waiting_screen_is_skippable_without_optional_flag():
    """connectOldPc flashed past in 6 s; a step on it must fall through once a later
    target shows, even when the YAML forgot optional: true."""
    m = Model("t")
    m.add(State("brief", "screen", "waiting", text=TextMatch(all=("brief",)), next=("next",)))
    m.add(State("next", "screen", "user", text=TextMatch(all=("next",)),
                actions={"go": Action("go", lambda ctx, a: None)}))
    seen = [Observation("next", None, None)]

    class Obs:
        def observe(self, s):
            return seen[0]

    script = RoleScript("t", [Step("brief", "publish", index=0), Step("next", done=True, index=1)], step_timeout=30, tick=1)
    m.get("brief").actions["publish"] = Action("publish", lambda ctx, a: pytest.fail("should have been skipped"))
    clock = {"now": 0.0}
    ctx = RunContext(role="t", run_id="r", session=None, app=object(), coordination=None, log=logger)
    Runner(m, script, ctx, Obs(), sleep=lambda s: clock.__setitem__("now", clock["now"] + s),
           clock=lambda: clock["now"]).run()


# ---------------------------------------------------------------- RCA 3: stale coordination values

class FakeCoordination:
    def __init__(self, sequence):
        self.sequence = list(sequence)

    def wait_for(self, run_id, key, timeout):
        value = self.sequence.pop(0) if len(self.sequence) > 1 else self.sequence[0]
        if value is None:
            raise TimeoutError
        return value

    def publish(self, run_id, key, value):
        pass


def test_peer_value_left_over_from_a_previous_run_is_ignored_until_it_changes(monkeypatch):
    monkeypatch.setattr(peer.time, "sleep", lambda s: None)
    # "finished" is already there from the last run with this id; then the peer writes
    # "started", then "finished" for real
    ctx = RunContext(role="source", run_id="r", session=None, app=None, log=logger,
                     coordination=FakeCoordination(["finished", "finished", "started", "finished"]))
    peer.snapshot_stale_value(ctx, "target_state")
    assert ctx.scratch["stale_values"]["target_state"] == "finished"
    seen = []
    original = ctx.coordination.wait_for

    def spy(run_id, key, timeout):
        v = original(run_id, key, timeout)
        seen.append(v)
        return v

    ctx.coordination.wait_for = spy
    peer.wait_for_peer_state(ctx, "target_state", ["finished", "failed"], timeout=60)
    assert seen == ["finished", "started", "finished"], "the stale 'finished' must not satisfy the wait"


def test_fresh_value_without_a_stale_snapshot_is_accepted_at_once(monkeypatch):
    monkeypatch.setattr(peer.time, "sleep", lambda s: None)
    ctx = RunContext(role="source", run_id="r", session=None, app=None, log=logger,
                     coordination=FakeCoordination(["finished"]))
    peer.wait_for_peer_state(ctx, "target_state", "finished", timeout=10)


# ---------------------------------------------------------------- RCA 4: unhandled endings

def test_lint_flags_an_ending_no_later_step_handles():
    m = Model("t")
    m.add(State("start", "screen", "user", text=TextMatch(all=("start",)),
                actions={"go": Action("go", lambda c, a: None, expect=("good", "bad"))}))
    m.add(State("good", "screen", "user", text=TextMatch(all=("good",))))
    m.add(State("bad", "screen", "user", text=TextMatch(all=("bad",))))
    m.add(State("busy", "screen", "waiting", text=TextMatch(all=("busy",)), next=("good", "bad")))
    one_sided = RoleScript("t", [Step("start", "go", index=0), Step("good", done=True, index=1)])
    assert any("'bad'" in w for w in lint_role_script(one_sided, m))
    both = RoleScript("t", [Step("start", "go", index=0), Step(["good", "bad"], done=True, index=1)])
    assert lint_role_script(both, m) == []
    # an explicit expect: is the author's word and silences the warning
    narrowed = RoleScript("t", [Step("start", "go", expect=["good"], index=0), Step("good", done=True, index=1)])
    assert lint_role_script(narrowed, m) == []
    # waiting screens are passed through, their endings still count
    via_busy = RoleScript("t", [Step("start", "go", expect=["busy"], index=0), Step("good", done=True, index=1)])
    assert any("'bad'" in w for w in lint_role_script(via_busy, m))
