"""poll_until(...) -- the one shared explicit-wait primitive used everywhere. See PROJECT_PLAN.md Sec 4.4.1."""

import time
from typing import Callable, TypeVar

T = TypeVar("T")


def poll_until(
    condition_fn: Callable[[], T],
    timeout: float,
    interval: float = 0.5,
    ignored_exceptions: tuple = (),
) -> T:
    """Confirmed live (2026-10-09, via code review): this used to always sleep the full
    `interval` after a failed attempt before re-checking the deadline -- so a caller
    requesting a short timeout (e.g. timeout=0.1 with the default interval=0.5) paid the
    full 0.5s on every miss instead of ~0.1s, silently costing 5x the requested budget.
    Sleeps min(interval, remaining time) instead, so a short timeout is actually short;
    behavior for the common case (timeout >> interval) is unchanged, since remaining
    time almost always exceeds interval there anyway.
    """
    deadline = time.monotonic() + timeout
    last_exc = None
    while time.monotonic() < deadline:
        try:
            result = condition_fn()
            if result:
                return result
        except ignored_exceptions as exc:
            last_exc = exc
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(interval, remaining))
    raise TimeoutError(f"Condition not met within {timeout}s") from last_exc
