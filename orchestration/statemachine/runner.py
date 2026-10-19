"""The runner loop -- the single place "wait for a screen while handling whatever pops
up" lives. Replaces the per-flow polling loops in flows/target/*.py.

Per tick:
  1. observe()                                    -> (screen, overlay, close_prompt)
  2. one of the step's targets is showing          -> perform its action / env step, done
  3. the step is optional and the NEXT step's target is showing -> skip this step
  4. a close prompt or an overlay (not the step's own target) -> apply the role's
     policy for it (click / wait_until_gone / fail / ignore; a missing policy falls back
     to the model: auto-recovering overlays are waited out, everything else fails)
  5. otherwise the screen must be one we could legitimately be passing through
     (previous target, the action's expect list, and anything the engine reaches on
     its own from there) -> keep waiting; anything else is an UnexpectedState
  6. step timeout -> StepTimeout, carrying the exact last observation

Every state change is recorded to ActionReporter (with a screenshot) so the HTML report
reads as a timeline of states, not just clicks. Failures carry the Observation, so the
message says where the app actually was.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from orchestration.statemachine.context import RunContext
from orchestration.statemachine.model import Model, State
from orchestration.statemachine.observer import Observation, Observer
from orchestration.statemachine.scenario import Policy, RoleScript, Step
from utils import environment

DEFAULT_AUTO_RECOVER_CAP_SECONDS = 600.0
DEFAULT_CLICK_POLICY_MAX = 5
# After clicking something, the same screen/overlay can still be rendered on the next tick
# (and a WebView2 click can lag) -- within this window a still-showing state is treated as
# "settling", not as a reason to click again. Mirrors flows/target/transfer_flow.py's
# RECLICK_INTERVAL_SECONDS.
DEFAULT_SETTLE_SECONDS = 3.0


class RunnerError(Exception):
    def __init__(self, message: str, observation: Observation | None = None, step: Step | None = None):
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
    last_click: float | None = None
    logged_wait: bool = False
    failed_clicks: int = 0


MAX_FAILED_POLICY_CLICKS = 2   # a click that fails because the dialog has just gone is not a finding; two in a row are


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
        self.model = model
        self.script = script
        self.ctx = ctx
        self.observer = observer
        self.reporter = reporter
        self._sleep = sleep
        self._clock = clock
        self.settle_seconds = settle_seconds
        self.log = ctx.log
        self.history: list[Observation] = []
        self._last: Observation | None = None
        self._tracking: dict[str, _OverlayTracking] = {}
        self._previous_target: str | None = None
        self._previous_action_expect: tuple = ()
        self._last_action_at: float | None = None
        self._previous_action = None          # the last model Action performed (None after a wait/env step)
        self._previous_action_args: dict = {}
        self._action_attempts = 0

    # ------------------------------------------------------------------ public

    def run(self) -> None:
        steps = self.script.steps
        self.log.info(f"Runner starting: {len(steps)} steps, role={self.ctx.role}")
        for i, step in enumerate(steps):
            self._run_step(step, steps[i + 1:])
            if step.done:
                self.log.success(f"Scenario script complete at {'/'.join(step.at)}")
                return
        self.log.success("Scenario script complete")

    # ------------------------------------------------------------------ one step

    def _run_step(self, step: Step, later_steps: list | None = None) -> None:
        timeout = step.timeout if step.timeout is not None else self.script.step_timeout
        deadline = self._clock() + timeout
        transit = self._transit_states(step)
        # an optional step is skipped the moment the app is at ANY later step's target --
        # confirmed necessary live (2026-10-19): after View details the app lands on
        # either complete or skippedFiles, and the branch not taken must fall through
        # Systemic fix (2026-10-20: connectOldPc flashed past in 6 s and a step waited 900 s
        # for it): a step whose every target is an engine-driven 'waiting' screen can be
        # skipped by the app itself, so it is optional whether or not the YAML says so.
        skippable = step.optional or all(self.model.get(t).kind == "waiting" for t in step.at)
        later_targets = {t for s in (later_steps or []) for t in s.at} if skippable else set()
        self.log.info(f"{step.label()} -- waiting up to {timeout:.0f}s" + (f" ({step.note})" if step.note else ""))

        while True:
            obs = self.observer.observe(self.ctx.app)
            self._note(obs)

            if obs.error:
                if self._clock() >= deadline:
                    raise StepTimeout(f"could not observe the app: {obs.error}", obs, step)
                self._sleep(self.script.tick)
                continue

            matched = self._at_target(obs, step)
            if matched is not None and not step.is_wait and self.model.get(matched).layer != "screen" \
                    and not self._confirmed_showing(self.model.get(matched)):
                matched = None  # a dialog's text lingering in the snapshot after it closed -- keep looking
            if matched is not None:
                self._perform(step, obs, matched)
                self._previous_target = matched
                return

            if skippable and obs.top() in later_targets:
                self.log.info(f"{step.label()} skipped -- {obs.top()} (a later step's target) is already showing")
                return

            if self._maybe_perform_again(obs):
                self._sleep(self.script.tick)
                continue

            interrupter = obs.close_prompt or obs.overlay
            if interrupter is not None:
                if not self._settling(interrupter):
                    self._apply_policy(interrupter, obs, step)
                if self._clock() >= deadline:
                    raise StepTimeout(f"{'/'.join(step.at)} never showed; {interrupter} kept interrupting", obs, step)
                self._sleep(self.script.tick)
                continue

            if obs.screen is not None:
                screen = self.model.get(obs.screen)
                if screen.terminal:
                    raise TerminalState(f"reached terminal state {obs.screen}", obs, step)
                if obs.screen not in transit:
                    raise UnexpectedState(
                        f"expected {'/'.join(step.at)} (or in transit via {sorted(transit)}), got {obs.screen}",
                        obs, step,
                    )
            # obs.screen is None: mid-transition or nothing recognised yet -- keep waiting

            if self._clock() >= deadline:
                raise StepTimeout(f"{'/'.join(step.at)} did not appear within {timeout:.0f}s", obs, step)
            self._sleep(self.script.tick)

    def _maybe_perform_again(self, obs: Observation) -> bool:
        """The WebView2 "click reported success but nothing happened" guard (CLAUDE.md
        Gotchas): if the state we last acted on is still showing reclick_after seconds
        later, perform the same action again, up to max_action_attempts in total. Only
        for idempotent actions (plain clicks); sign-in, code entry, peer publishes and
        env steps are never repeated this way."""
        action = self._previous_action
        if action is None or not action.idempotent or obs.top() != self._previous_target:
            return False
        if self._last_action_at is None or (self._clock() - self._last_action_at) < self.script.reclick_after:
            return False
        if self._action_attempts >= self.script.max_action_attempts:
            return False
        self._action_attempts += 1
        self.log.warning(
            f"{self._previous_target} still showing {self.script.reclick_after:.0f}s after {action.name} -- "
            f"performing it again (attempt {self._action_attempts}/{self.script.max_action_attempts})"
        )
        start = self._clock()
        try:
            action.perform(self.ctx, self._previous_action_args)
        except Exception as exc:
            self._record(self._previous_target, f"{action.name} (retry)", "fail", (self._clock() - start) * 1000,
                         error=str(exc))
            raise RunnerError(f"{action.name} on {self._previous_target} failed on retry: {exc}", obs) from exc
        self._record(self._previous_target, f"{action.name} (retry {self._action_attempts})", "pass",
                     (self._clock() - start) * 1000)
        self._last_action_at = self._clock()
        return True

    def _settling(self, state_id: str) -> bool:
        """True while the state we just acted on may still be rendered (see
        DEFAULT_SETTLE_SECONDS) -- it is not an interruption yet."""
        if self._last_action_at is None or state_id != self._previous_target:
            return False
        if (self._clock() - self._last_action_at) < self.settle_seconds:
            return True
        # still the state we just acted on, and a re-performance is still allowed:
        # give _maybe_perform_again its turn before any policy judges the overlay
        action = self._previous_action
        return action is not None and action.idempotent and self._action_attempts < self.script.max_action_attempts

    def _at_target(self, obs: Observation, step: Step) -> str | None:
        """The step target that is showing right now, or None."""
        for target in step.at:
            state = self.model.get(target)
            if state.layer == "screen":
                # a screen step is only "reached" when nothing is stacked over it
                if obs.screen == target and obs.overlay is None and obs.close_prompt is None:
                    return target
            elif state.layer == "overlay":
                if obs.overlay == target and obs.close_prompt is None:
                    return target
            elif obs.close_prompt == target:
                return target
        return None

    def _transit_states(self, step: Step) -> set:
        """Screens we may legitimately see while waiting for this step's target."""
        seeds = set(step.at)
        if self._previous_target:
            seeds.add(self._previous_target)
        seeds.update(self._previous_action_expect)
        if step.expect:
            seeds.update(step.expect)
        reachable = self.model.reachable_on_its_own(seeds)
        # a previous *user* state we just acted on may still be rendering for a moment
        return reachable | seeds

    def _perform(self, step: Step, obs: Observation, matched: str) -> None:
        if step.wait_before:
            self.log.info(f"{step.label()} reached -- pausing {step.wait_before:.0f}s before acting")
            self._sleep(step.wait_before)
        self._previous_action = None
        self._action_attempts = 0
        if step.is_wait:
            self.log.success(f"{step.label()} reached")
            self._previous_action_expect = tuple(step.expect) if step.expect else ()
            return

        if step.env is not None:
            name, perform, default_expect = step.env, environment.resolve(step.env), ()
            perform_args = (self.ctx,)
        else:
            action = self.model.get(matched).action(step.do)
            name, perform, default_expect = action.name, action.perform, action.expect
            perform_args = (self.ctx, step.args)
            self._previous_action, self._previous_action_args, self._action_attempts = action, step.args, 1

        self.log.info(f"{step.label()} -- performing {name}" + (f" {step.args}" if step.args else ""))
        start = self._clock()
        try:
            perform(*perform_args)
        except Exception as exc:
            self._record(matched, name, "fail", (self._clock() - start) * 1000, error=str(exc))
            raise RunnerError(f"{name} on {matched} failed: {exc}", obs, step) from exc
        self._record(matched, name, "pass", (self._clock() - start) * 1000)
        self._last_action_at = self._clock()
        self._previous_action_expect = tuple(step.expect) if step.expect else tuple(default_expect)

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
            if not self._confirmed_showing(state):
                return  # the snapshot still carries the text, but the dialog is not really there
            action = state.action(policy.action)
            self.log.warning(f"{state_id} appeared -- policy: {action.name}")
            start = self._clock()
            try:
                action.perform(self.ctx, {})
            except Exception as exc:
                # Confirmed live (2026-10-20): Continue on the account-mismatch dialog
                # 'failed' because the dialog had just closed while its text still showed.
                # A policy click is opportunistic: one failure is re-observed, not fatal.
                track.failed_clicks += 1
                track.last_click = self._clock()
                self._record(state_id, action.name, "fail", (self._clock() - start) * 1000, error=str(exc))
                if track.failed_clicks >= MAX_FAILED_POLICY_CLICKS:
                    raise RunnerError(
                        f"policy action {action.name} on {state_id} failed {track.failed_clicks} times: {exc}", obs, step
                    ) from exc
                self.log.warning(f"policy action {action.name} on {state_id} failed ({exc}) -- re-observing first")
                return
            track.clicks += 1
            track.last_click = self._clock()
            self._record(state_id, action.name, "pass", (self._clock() - start) * 1000)
            return
        raise RunnerError(f"unknown policy kind {policy.kind!r} for {state_id}", obs, step)

    def _confirmed_showing(self, state: State) -> bool:
        """Before acting on a dialog, check its own locator once (the snapshot can carry a
        closed dialog's text for a while). No probe -> trust the observation."""
        if state.probe is None:
            return True
        try:
            present = bool(state.probe(self.ctx.app, timeout=1.0))
        except Exception:  # noqa: BLE001 -- a probe error must not change the decision
            return True
        if not present:
            self.log.info(f"{state.id} is in the snapshot but its locator is not found -- treating it as gone")
        return present

    def _describe(self, state: State) -> str:
        reader = state.actions.get("read_text")
        if reader is None:
            return ""
        try:
            text = reader.perform(self.ctx, {})
            return f": {text}" if text else ""
        except Exception:  # noqa: BLE001 -- describing a failure must not replace it
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
                error: str | None = None, screenshot: bool = False) -> None:
        if self.reporter is None:
            return
        shot = shot_err = None
        if screenshot or status == "fail":
            try:
                shot, shot_err = self.reporter.capture_screenshot(self.ctx.app, component, action)
            except Exception as exc:  # noqa: BLE001 -- evidence capture never masks the real result
                shot_err = str(exc)
        try:
            self.reporter.record(component=component, action=action, status=status, duration_ms=duration_ms,
                                 error=error, screenshot=shot, screenshot_error=shot_err)
        except Exception as exc:  # noqa: BLE001 -- reporting problems are logged, never fatal
            self.log.warning(f"could not record {component}/{action}: {exc}")
