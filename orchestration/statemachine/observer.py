"""Observers: turn the live app into an Observation (screen, overlay, close_prompt).

SnapshotObserver -- one WinAppDriver /source call per tick, then every State's TextMatch
is evaluated against that one normalized string. Round-trips per tick: 1, regardless of
how many states the model has. This relies on page_source containing the WebView2
content, which the existing assertions/target/migration_preparation_transition.py already
depends on (confirmed live in SignInFlow logs: "transition screen detected"), but the
full-tree behaviour for every screen is NOT yet confirmed live -- hence the fallback.

ProbeObserver -- calls each State's probe (its assertions module's is_showing) with a
short timeout. One find_element round-trip per state per tick; slow with a large model,
but uses exactly the locators the rest of the framework already trusts. Selected with
--observer probe.

Layer precedence is fixed: close prompts over overlays over screens, matching the app's
own stacking (TARGET_STATE_MACHINE.md Sec 1).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from loguru import logger

from orchestration.statemachine.model import Model, State, normalize


@dataclass
class Observation:
    screen: str | None
    overlay: str | None
    close_prompt: str | None
    error: str | None = None
    at: float = field(default_factory=time.monotonic)
    snapshot_len: int = 0
    via: str = "snapshot"

    def key(self) -> str:
        return (
            f"screen={self.screen or '-'} overlay={self.overlay or '-'} "
            f"prompt={self.close_prompt or '-'}"
            + (f" via={self.via}" if self.via != "snapshot" else "")
            + (f" error={self.error!r}" if self.error else "")
        )

    def top(self) -> str | None:
        """The state id that currently has the user's attention."""
        return self.close_prompt or self.overlay or self.screen

    def same_as(self, other: Observation | None) -> bool:
        return (
            other is not None
            and self.screen == other.screen
            and self.overlay == other.overlay
            and self.close_prompt == other.close_prompt
            and bool(self.error) == bool(other.error)
        )


class Observer(Protocol):
    def observe(self, session) -> Observation: ...


def _first_match(states, predicate: Callable[[State], bool]) -> str | None:
    for state in states:
        try:
            if predicate(state):
                return state.id
        except Exception as exc:  # noqa: BLE001 -- a broken detector must not take the whole tick down
            logger.warning(f"detector for {state.id!r} raised {exc!r} -- treated as not showing")
    return None


class SnapshotObserver:
    def __init__(self, model: Model, source_fn: Callable[[object], str] | None = None):
        self.model = model
        self._source_fn = source_fn or (lambda session: session.page_source)
        self.last_snapshot: str = ""

    def observe(self, session) -> Observation:
        try:
            raw = self._source_fn(session) or ""
        except Exception as exc:  # noqa: BLE001 -- any /source failure is reported as an observation error
            return Observation(None, None, None, error=f"{type(exc).__name__}: {exc}")
        snapshot = normalize(raw)
        self.last_snapshot = snapshot

        def showing(state: State) -> bool:
            if state.text is not None:
                return state.text.matches(snapshot)
            return False  # probe-only states are invisible to the snapshot observer

        return Observation(
            screen=_first_match(self.model.screens(), showing),
            overlay=_first_match(self.model.overlays(), showing),
            close_prompt=_first_match(self.model.close_prompts(), showing),
            snapshot_len=len(snapshot),
        )


class ProbeObserver:
    def __init__(self, model: Model, probe_timeout: float = 0.3):
        self.model = model
        self.probe_timeout = probe_timeout

        self._last_screen: str | None = None

    def _screen_order(self) -> list:
        """Sticky ordering -- confirmed live (2026-10-19): probing every screen in turn
        costs ~0.3-0.6 s each, ~15 s per tick with 20+ screens. The screen seen last is
        far more likely to still be showing, so it is probed right after any screen that
        outranks it; if it is still there, the lower-ranked screens are skipped."""
        screens = self.model.screens()
        if self._last_screen is None:
            return screens
        last = self.model.get(self._last_screen)
        ahead = [s for s in screens if s.priority > last.priority]
        rest = [s for s in screens if s.priority <= last.priority and s.id != last.id]
        return ahead + [last] + rest

    def observe(self, session) -> Observation:
        def showing(state: State) -> bool:
            if state.probe is None:
                return False
            return bool(state.probe(session, timeout=self.probe_timeout))

        try:
            screen = _first_match(self._screen_order(), showing)
            self._last_screen = screen or self._last_screen
            return Observation(
                screen=screen,
                overlay=_first_match(self.model.overlays(), showing),
                close_prompt=_first_match(self.model.close_prompts(), showing),
                via="probe",
            )
        except Exception as exc:  # noqa: BLE001 -- same: reported, never raised from a tick
            return Observation(None, None, None, error=f"{type(exc).__name__}: {exc}", via="probe")


class HybridObserver:
    """Snapshot first; probe when the snapshot cannot be trusted.

    Confirmed live (2026-10-19, first scenario_runner run): WinAppDriver answered
    GET /source with HTTP 400 once the Target app reached the code-entry screen, after
    serving earlier screens fine -- the snapshot observer alone goes blind exactly when
    the UI tree gets complicated. This observer falls back to per-locator probing when
    the snapshot call errors, and also after `probe_after_blank` consecutive snapshots
    that recognised nothing (a screen whose text the snapshot does not carry). Probing is
    slower (one find_element per state), so it is only used while the snapshot is
    failing; a recognised snapshot resets the counter."""

    def __init__(self, model: Model, probe_timeout: float = 0.3, probe_after_blank: int = 3):
        self.snapshot = SnapshotObserver(model)
        self.probe = ProbeObserver(model, probe_timeout=probe_timeout)
        self.probe_after_blank = probe_after_blank
        self._blank_streak = 0

    def observe(self, session) -> Observation:
        obs = self.snapshot.observe(session)
        if obs.error:
            logger.debug(f"snapshot failed ({obs.error}) -- probing instead")
            probed = self.probe.observe(session)
            if probed.error:
                probed.error = f"snapshot: {obs.error}; probe: {probed.error}"
            return probed
        if obs.top() is None:
            self._blank_streak += 1
            if self._blank_streak >= self.probe_after_blank:
                logger.debug(f"{self._blank_streak} blank snapshots -- probing instead")
                return self.probe.observe(session)
            return obs
        self._blank_streak = 0
        if obs.screen is not None:
            self.probe._last_screen = obs.screen  # keep the probe's sticky order current
        return obs
