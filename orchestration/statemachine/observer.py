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
from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol

from loguru import logger

from orchestration.statemachine.model import Model, State, normalize


@dataclass
class Observation:
    screen: Optional[str]
    overlay: Optional[str]
    close_prompt: Optional[str]
    error: Optional[str] = None
    at: float = field(default_factory=time.monotonic)
    snapshot_len: int = 0

    def key(self) -> str:
        return (
            f"screen={self.screen or '-'} overlay={self.overlay or '-'} "
            f"prompt={self.close_prompt or '-'}" + (f" error={self.error!r}" if self.error else "")
        )

    def top(self) -> Optional[str]:
        """The state id that currently has the user's attention."""
        return self.close_prompt or self.overlay or self.screen

    def same_as(self, other: Optional["Observation"]) -> bool:
        return (
            other is not None
            and self.screen == other.screen
            and self.overlay == other.overlay
            and self.close_prompt == other.close_prompt
            and bool(self.error) == bool(other.error)
        )


class Observer(Protocol):
    def observe(self, session) -> Observation: ...


def _first_match(states, predicate: Callable[[State], bool]) -> Optional[str]:
    for state in states:
        try:
            if predicate(state):
                return state.id
        except Exception as exc:  # a broken detector must not take the whole tick down
            logger.warning(f"detector for {state.id!r} raised {exc!r} -- treated as not showing")
    return None


class SnapshotObserver:
    def __init__(self, model: Model, source_fn: Optional[Callable[[object], str]] = None):
        self.model = model
        self._source_fn = source_fn or (lambda session: session.page_source)
        self.last_snapshot: str = ""

    def observe(self, session) -> Observation:
        try:
            raw = self._source_fn(session) or ""
        except Exception as exc:
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

    def observe(self, session) -> Observation:
        def showing(state: State) -> bool:
            if state.probe is None:
                return False
            return bool(state.probe(session, timeout=self.probe_timeout))

        try:
            return Observation(
                screen=_first_match(self.model.screens(), showing),
                overlay=_first_match(self.model.overlays(), showing),
                close_prompt=_first_match(self.model.close_prompts(), showing),
            )
        except Exception as exc:
            return Observation(None, None, None, error=f"{type(exc).__name__}: {exc}")
