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
    deadline = time.monotonic() + timeout
    last_exc = None
    while time.monotonic() < deadline:
        try:
            result = condition_fn()
            if result:
                return result
        except ignored_exceptions as exc:
            last_exc = exc
        time.sleep(interval)
    raise TimeoutError(f"Condition not met within {timeout}s") from last_exc
