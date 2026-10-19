"""The transition table as data.

A Model is a dict of State objects for one role. Each State says which layer it lives in
(screen / overlay / close_prompt), how to detect it (a TextMatch over a page_source
snapshot, and/or a probe function such as an assertions module's is_showing), which
actions a scenario may perform on it, and which states the engine may move to on its
own. The runner never hard-codes any of this -- it only reads the Model.

Detection text is normalized on both sides (see normalize()): HTML/XML entities decoded,
curly quotes straightened, lower-cased, whitespace collapsed -- so a match term can be
typed plainly and still survive the apostrophe trap described in CLAUDE.md's Gotchas.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any, Literal

Layer = Literal["screen", "overlay", "close_prompt"]
Kind = Literal["user", "waiting", "peer", "terminal"]

_QUOTE_MAP = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"', "—": "-", "–": "-"})
_WS = re.compile(r"\s+")


class ModelError(Exception):
    pass


def normalize(text: str) -> str:
    """Normalize UI text or a page_source dump for substring matching."""
    if not text:
        return ""
    text = html.unescape(text)
    text = text.translate(_QUOTE_MAP)
    text = text.lower()
    return _WS.sub(" ", text).strip()


@dataclass(frozen=True)
class TextMatch:
    """Substring predicate over a normalized snapshot. `all` terms must every one be
    present, at least one of `any` must be present (if given), and no `none` term may be
    present. Terms are normalized at construction."""

    all: tuple[str, ...] = ()
    any: tuple[str, ...] = ()
    none: tuple[str, ...] = ()

    def __post_init__(self):
        object.__setattr__(self, "all", tuple(normalize(t) for t in self.all))
        object.__setattr__(self, "any", tuple(normalize(t) for t in self.any))
        object.__setattr__(self, "none", tuple(normalize(t) for t in self.none))
        if not self.all and not self.any:
            raise ModelError("TextMatch needs at least one 'all' or 'any' term")

    def matches(self, normalized_snapshot: str) -> bool:
        if any(t in normalized_snapshot for t in self.none):
            return False
        if not all(t in normalized_snapshot for t in self.all):
            return False
        if self.any and not any(t in normalized_snapshot for t in self.any):
            return False
        return True


@dataclass
class Action:
    """One thing a scenario may do while on a State. `perform(ctx, args)` is a plain
    callable; `expect` lists the state ids that may legitimately follow (used by the
    runner to tell 'in transit' from 'went somewhere wrong', and by scenario validation)."""

    name: str
    perform: Callable[..., Any]
    expect: tuple[str, ...] = ()
    description: str = ""


@dataclass
class State:
    id: str
    layer: Layer
    kind: Kind = "user"
    text: TextMatch | None = None
    probe: Callable[..., bool] | None = None
    actions: dict[str, Action] = field(default_factory=dict)
    next: tuple[str, ...] = ()
    auto_recovers: bool = False
    terminal: bool = False
    priority: int = 0
    description: str = ""

    def __post_init__(self):
        if self.text is None and self.probe is None:
            raise ModelError(f"State {self.id!r} has neither a text match nor a probe")
        if self.kind == "terminal":
            self.terminal = True

    def action(self, name: str) -> Action:
        try:
            return self.actions[name]
        except KeyError:
            raise ModelError(f"State {self.id!r} has no action {name!r} (has: {sorted(self.actions)})") from None


@dataclass
class Model:
    role: str
    states: dict[str, State] = field(default_factory=dict)

    def add(self, state: State) -> State:
        if state.id in self.states:
            raise ModelError(f"Duplicate state id {state.id!r}")
        self.states[state.id] = state
        return state

    def get(self, state_id: str) -> State:
        try:
            return self.states[state_id]
        except KeyError:
            raise ModelError(f"Unknown state {state_id!r} in model {self.role!r}") from None

    def has(self, state_id: str) -> bool:
        return state_id in self.states

    def by_layer(self, layer: Layer) -> list[State]:
        """States of one layer, highest priority first, insertion order within a tier."""
        ordered = [s for s in self.states.values() if s.layer == layer]
        return sorted(ordered, key=lambda s: -s.priority)

    def screens(self) -> list[State]:
        return self.by_layer("screen")

    def overlays(self) -> list[State]:
        return self.by_layer("overlay")

    def close_prompts(self) -> list[State]:
        return self.by_layer("close_prompt")

    def reachable_on_its_own(self, start_ids: Iterable[str]) -> set:
        """Closure of `next` from the given states: everything the engine may move to
        without a user action. Used by the runner to accept in-transit screens."""
        seen = set()
        stack = list(start_ids)
        while stack:
            sid = stack.pop()
            if sid in seen or not self.has(sid):
                continue
            seen.add(sid)
            stack.extend(self.get(sid).next)
        return seen

    def validate(self) -> None:
        """Every `next` and every action `expect` must name a known state."""
        problems = []
        for state in self.states.values():
            for nxt in state.next:
                if not self.has(nxt):
                    problems.append(f"{state.id}.next -> unknown state {nxt!r}")
            for action in state.actions.values():
                for exp in action.expect:
                    if not self.has(exp):
                        problems.append(f"{state.id}.{action.name}.expect -> unknown state {exp!r}")
        if problems:
            raise ModelError("Model " + self.role + " is inconsistent:\n  " + "\n  ".join(problems))
