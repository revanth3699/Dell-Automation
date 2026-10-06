"""
@retry: the one shared retry decorator for flaky WinAppDriver interactions. Formalizes
what used to be ad-hoc per-call retry loops (BaseComponent's old _with_stale_retry,
EmailStep/PasswordStep's own hand-rolled for-loops) into a single reusable pattern,
confirmed directly requested by the user (2026-10-06): "each interaction must be retried
if failed... decorator pattern for that."

Scope: this wraps a single low-level interaction (find-and-click, find-and-type) that can
fail transiently (e.g. a stale element reference across a page transition -- WinAppDriver
returns a plain 500 for this, not a distinguishable "stale element" error). It is
deliberately NOT used for higher-level business retries like "did the page actually
advance after submitting" or "did sign-in succeed" -- those are a different concern
(confirming an action's effect, not working around transient API flakiness) and stay as
explicit logic in the flow/component that owns that judgment call.
"""

import time
from functools import wraps
from typing import Tuple, Type


def retry(attempts: int = 2, delay: float = 0.5, exceptions: Tuple[Type[BaseException], ...] = (Exception,)):
    """Retries the decorated call up to `attempts` times on any of `exceptions`, sleeping
    `delay` seconds between attempts. Re-raises the last exception if every attempt fails.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc: BaseException
            for attempt in range(attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < attempts - 1:
                        time.sleep(delay)
            raise last_exc
        return wrapper
    return decorator
