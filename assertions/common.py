"""Common assertion methods shared by every assertions/<role>/<screen>.py module.

Each method takes a (by, value) locator tuple (plus a name for logging) and polls for
up to `timeout` seconds, returning True if the element was found within that time,
False otherwise -- never raises. This is the one place polling-for-an-assertion is
implemented; every segregated assertions/<role>/<screen>.py file imports from here and
passes it its own locator(s), rather than each screen re-implementing the same poll
loop. Flows then import and call the resulting is_X_showing()/is_X_confirmed()
functions directly, decoupling them from locators/ and from components/' own methods.
"""

from loguru import logger

from utils.wait_utils import poll_until


def _poll_for_element(session, locator: tuple, name: str, timeout: float):
    by, value = locator

    def _try():
        try:
            return session.find_element(by, value)
        except Exception:
            return None

    try:
        poll_until(_try, timeout=timeout, interval=0.5)
        found = True
    except TimeoutError:
        found = False
    logger.debug(f"exists check on {name!r} (timeout={timeout}s): {found}")
    return found


def text_exists(session, locator: tuple, name: str, timeout: float = 2.0) -> bool:
    """Polls for up to `timeout` seconds for the heading/body text identified by
    `locator`. Returns True if found within that time, False otherwise."""
    return _poll_for_element(session, locator, name, timeout)


def button_exists(session, locator: tuple, name: str, timeout: float = 2.0) -> bool:
    """Polls for up to `timeout` seconds for the button identified by `locator`.
    Same underlying check as text_exists() -- given its own name so call sites read
    clearly (asserting a button's presence vs a heading/body text's), per explicit
    user direction."""
    return _poll_for_element(session, locator, name, timeout)


def all_exist(session, checks: list, timeout: float = 2.0) -> bool:
    """True only if EVERY (locator, name) pair in `checks` exists within timeout --
    the "two-texts-stronger-than-one" gate pattern (e.g. a heading AND the body text
    under it, both required before a button is clicked), expressed generically instead
    of each screen hand-rolling its own `and` chain."""
    return all(text_exists(session, locator, name, timeout=timeout) for locator, name in checks)


def gone(session, locator: tuple, name: str, timeout: float, poll_interval: float = 0.5) -> bool:
    """True if `locator` becomes absent within timeout; False if it's still present
    once the timeout expires. NOT the same as "text_exists(...) is False with a long
    timeout": this polls until the element stops being found, rather than returning
    early the instant a single check happens to miss it mid-transition.
    """
    import time

    deadline = time.monotonic() + timeout
    while True:
        if not text_exists(session, locator, name, timeout=poll_interval):
            return True
        if time.monotonic() >= deadline:
            return False
