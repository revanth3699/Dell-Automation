"""The runner loop -- the single place "wait for a screen while handling whatever pops
up" lives. Replaces the per-flow polling loops in flows/target/*.py.

Per tick:
  1. observe()                                    -> (screen, overlay, close_prompt)
  2. a close prompt or an overlay that is NOT the step's own target -> apply the role's
     policy for it (click / wait_until_gone / fail / ignore; a missing policy falls back
     to the model: auto-recovering overlays are waited out, terminal ones fail)
  3. the step's target state is showing            -> perform its action (if any), done
  4. otherwise the screen must be one we could legitimately be passing through
     (previous target, the action's expect list, and anything the engine reaches on
     its own from there) -> keep waiting; anything else is an UnexpectedState
  5. step timeout -> StepTimeout, carrying the exact last observation

Every state change is recorded to ActionReporter (with a screenshot) so the HTML report
reads as a timeline of states, not just clicks. Failures carry the Observation, so the
message says where the app actually was.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from orchestration.statemachine.context import RunContext
from orchestration.statemachine.model import Model, State
from orchestration.statemachine.observer import Observation, Observer
from orchestration.statemachine.scenario import Policy, RoleScript, Step

DEFAULT_AUTO_RECOVER_CAP_SECONDS = 600.0
DEFAULT_CLICK_POLICY_MAX = 5
# After clicking something, the same screen/overlay can still be rendered on the next tick
# (and a WebView2 click can lag) -- within this window a still-showing state is treated as
# "settling", not as a reason to click again. Mirrors flows/target/transfer_flow.py's
# RECLICK_INTERVAL_SECONDS.
DEFAULT_SETTLE_SECONDS = 3.0


class RunnerError(Exception):
    def __init__(self, message: str, observation: Optional[Observation] = None, step: Optional[Step] = None):
        self.observation = observation
        self.step = step
        where = f" [{observation.key()}]" if observation else ""
        at = f" during {step.label()}" if step else ""
        super().__init__(f"{message}{at}{where}")


class StepTimeout(RunnerError):
    pass


class UnexpectedState(RunnerError):
    pass


class TerminalState(RunnerError):
    pass


class PolicyExhausted(RunnerError):
    pass


@dataclass
class _OverlayTracking:
    first_seen: float
    clicks: int = 0
    last_click: Optional[float] = None
    logged_wait: bool = False


class Runner:
    def __init__(
        self,
        model: Model,
        script: RoleScript,
        ctx: RunContext,
        observer: Observer,
        reporter=None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        settle_seconds: float = DEFAULT_SETTLE_SECONDS,
    ):
        self.settle_seconds = settle_seconds
        self._last_action_at: Optional[float] = None
        self.model = model
        self.script = script
        self.ctx = ctx
        self.observer = observer
        self.reporter = reporter
        self._sleep = sleep
        self._clock = clock
        self.log = ctx.log
        self.history: List[Observation] = []
        self._last: Optional[Observation] = None
        self._tracking: Dict[str, _OverlayTracking] = {}
        self._previous_target: Optional[str] = None
        self._previous_action_expect: tuple = ()

    # ------------------------------------------------------------------ public

    def run(self) -> None:
        self.log.info(f"Runner starting: {len(self.script.steps)} steps, role={self.ctx.role}")
        for step in self.script.steps:
            self._run_step(step)
            if step.done:
                self.log.success(f"Scenario script complete at {step.at}")
                return
        self.log.success("Scenario script complete")

    # ------------------------------------------------------------------ one step

    def _run_step(self, step: Step) -> None:
        timeout = step.timeout if step.timeout is not None else self.script.step_timeout
        deadline = self._clock() + timeout
        transit = self._transit_states(step)
        self.log.info(f"{step.label()} -- waiting up to {timeout:.0f}s" + (f" ({step.note})" if step.note else ""))

        while True:
            obs = self.observer.observe(self.ctx.app)
            self._note(obs)

            if obs.error:
                if self._clock() >= deadline:
                    raise StepTimeout(f"could not observe the app: {obs.error}", obs, step)
                self._sleep(self.script.tick)
                continue

            if self._at_target(obs, step):
                self._perform(step, obs)
                self._previous_target = step.at
                return

            interrupter = obs.close_prompt or obs.overlay
            if interrupter is not None:
                if not self._settling(interrupter):
                    self._apply_policy(interrupter, obs, step)
                if self._clock() >= deadline:
                    raise StepTimeout(f"{step.at} never showed; {interrupter} kept interrupting", obs, step)
                self._sleep(self.script.tick)
                continue

            if obs.screen is None:
                pass  # mid-transition or nothing recognised yet -- keep waiting
            else:
                screen = self.model.get(obs.screen)
                if screen.terminal:
                    raise TerminalState(f"reached terminal state {obs.screen}", obs, step)
                if obs.screen not in transit:
                    raise UnexpectedState(
                        f"expected {step.at} (or in transit via {sorted(transit)}), got {obs.screen}", obs, step
                    )

            if self._clock() >= deadline:
                raise StepTimeout(f"{step.at} did not appear within {timeout:.0f}s", obs, step)
            self._sleep(self.script.tick)

    def _settling(self, state_id: str) -> bool:
        """True while the state we just acted on may still be rendered (see
        DEFAULT_SETTLE_SECONDS) -- it is not an interruption yet."""
        if self._last_action_at is None or state_id != self._previous_target:
            return False
        return (self._clock() - self._last_action_at) < self.settle_seconds

    def _at_target(self, obs: Observation, step: Step) -> bool:
        target = self.model.get(step.at)
        if target.layer == "screen":
            # a screen step is only "reached" when nothing is stacked over it
            return obs.screen == step.at and obs.overlay is None and obs.close_prompt is None
        if target.layer == "overlay":
            return obs.overlay == step.at and obs.close_prompt is None
        return obs.close_prompt == step.at

    def _transit_states(self, step: Step) -> set:
        """Screens we may legitimately see while waiting for this step's target."""
        seeds = {step.at}
        if self._previous_target:
            seeds.add(self._previous_target)
        seeds.update(self._previous_action_expect)
        if step.expect:
            seeds.update(step.expect)
        reachable = self.model.reachable_on_its_own(seeds)
        # a previous *user* state we just acted on may still be rendering for a moment
        return reachable | seeds

    def _perform(self, step: Step, obs: Observation) -> None:
        if step.is_wait:
            self.log.success(f"{step.label()} reached")
            self._previous_action_expect = ()
            return
        state = self.model.get(step.at)
        action = state.action(step.do)
        self.log.info(f"{step.label()} -- performing {action.name}" + (f" {step.args}" if step.args else ""))
        start = self._clock()
        try:
            action.perform(self.ctx, step.args)
        except Exception as exc:
            self._record(step.at, action.name, "fail", (self._clock() - start) * 1000, error=str(exc))
            raise RunnerError(f"action {action.name} on {step.at} failed: {exc}", obs, step) from exc
        self._record(step.at, action.name, "pass", (self._clock() - start) * 1000)
        self._last_action_at = self._clock()
        self._previous_action_expect = tuple(step.expect) if step.expect else action.expect

    # ------------------------------------------------------------------ policies

    def _policy_for(self, state: State) -> Policy:
        explicit = self.script.policies.get(state.id)
        if explicit is not None:
            return explicit
        if state.terminal:
            return Policy(kind="fail")
        if state.auto_recovers:
            return Policy(kind="wait_until_gone", cap=DEFAULT_AUTO_RECOVER_CAP_SECONDS)
        return Policy(kind="fail")  # an unpoliced, non-recovering overlay is a real finding

    def _apply_policy(self, state_id: str, obs: Observation, step: Step) -> None:
        state = self.model.get(state_id)
        policy = self._policy_for(state)
        track = self._tracking.setdefault(state_id, _OverlayTracking(first_seen=self._clock()))

        if policy.kind == "ignore":
            return
        if policy.kind == "fail":
            raise TerminalState(f"{state_id} appeared (policy: fail)" + self._describe(state), obs, step)
        if policy.kind == "wait_until_gone":
            cap = policy.cap if policy.cap is not None else DEFAULT_AUTO_RECOVER_CAP_SECONDS
            waited = self._clock() - track.first_seen
            if waited > cap:
                raise PolicyExhausted(f"{state_id} still showing after {cap:.0f}s (policy: wait_until_gone)", obs, step)
            if not track.logged_wait:
                self.log.warning(f"{state_id} showing -- waiting for it to clear (cap {cap:.0f}s)")
                track.logged_wait = True
            return
        if policy.kind == "click":
            if track.last_click is not None and (self._clock() - track.last_click) < self.settle_seconds:
                return  # just clicked it; give the UI a moment before judging
            limit = policy.max_times if policy.max_times is not None else DEFAULT_CLICK_POLICY_MAX
            if track.clicks >= limit:
                raise PolicyExhausted(
                    f"{state_id}: policy action {policy.action} already applied {track.clicks} times", obs, step
                )
            action = state.action(policy.action)
            self.log.warning(f"{state_id} appeared -- policy: {action.name}")
            start = self._clock()
            try:
                action.perform(self.ctx, {})
            except Exception as exc:
                self._record(state_id, action.name, "fail", (self._clock() - start) * 1000, error=str(exc))
                raise RunnerError(f"policy action {action.name} on {state_id} failed: {exc}", obs, step) from exc
            track.clicks += 1
            track.last_click = self._clock()
            self._record(state_id, action.name, "pass", (self._clock() - start) * 1000)
            return
        raise RunnerError(f"unknown policy kind {policy.kind!r} for {state_id}", obs, step)

    def _describe(self, state: State) -> str:
        reader = state.actions.get("read_text")
        if reader is None:
            return ""
        try:
            text = reader.perform(self.ctx, {})
            return f": {text}" if text else ""
        except Exception:
            return ""

    # ------------------------------------------------------------------ bookkeeping

    def _note(self, obs: Observation) -> None:
        if obs.same_as(self._last):
            return
        self.history.append(obs)
        self._last = obs
        # overlays that went away get their tracking reset so a re-appearance counts afresh
        for sid in list(self._tracking):
            if sid not in (obs.overlay, obs.close_prompt):
                del self._tracking[sid]
        self.log.info(f"state: {obs.key()}")
        self._record("StateMachine", f"observe {obs.key()}", "pass", 0.0, screenshot=True)

    def _record(self, component: str, action: str, status: str, duration_ms: float,
                error: Optional[str] = None, screenshot: bool = False) -> None:
        if self.reporter is None:
            return
        shot = shot_err = None
        if screenshot or status == "fail":
            try:
                shot, shot_err = self.reporter.capture_screenshot(self.ctx.app, component, action)
            except Exception as exc:  # evidence capture never masks the real result
                shot_err = str(exc)
        try:
            self.reporter.record(component=component, action=action, status=status, duration_ms=duration_ms,
                                 error=error, screenshot=shot, screenshot_error=shot_err)
        except Exception as exc:
            self.log.warning(f"could not record {component}/{action}: {exc}")
