"""
BaseComponent: wraps a WinAppDriverSession + locator with explicit-wait find, click,
type, and a screenshot taken after every action. See PROJECT_PLAN.md Sec 4.4.

Minimal version -- full ActionReporter/report.html wiring (Sec 4.8) not built yet;
screenshots are saved to reports/output/ with a timestamped filename in the meantime so
nothing is lost once that layer exists.
"""

import time
from pathlib import Path
from typing import Optional

from loguru import logger

from factory.logger_factory import LoggerFactory
from factory.retry import retry
from factory.wait_utils import poll_until

LoggerFactory.ensure_console()  # colored console logging works even before any flow
                                 # calls LoggerFactory.get_logger(role)

SCREENSHOT_DIR = Path(__file__).resolve().parent.parent / "reports" / "output" / "screenshots"


class ComponentActionError(Exception):
    pass


class BaseComponent:
    def __init__(self, session, by: str, locator: str, name: str, timeout: float = 10.0):
        self.session = session
        self.by = by
        self.locator = locator
        self.name = name
        self.timeout = timeout

    def _find(self):
        def _try():
            try:
                return self.session.find_element(self.by, self.locator)
            except Exception:
                return None

        element = poll_until(_try, timeout=self.timeout, interval=0.5)
        return element

    def _screenshot(self, action: str) -> str:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"{int(time.time() * 1000)}_{self.name.replace(' ', '_')}_{action}.png"
        path = SCREENSHOT_DIR / filename
        try:
            path.write_bytes(self.session.get_screenshot_as_png())
        except Exception:
            pass  # evidence capture must never mask the real failure
        return str(path)

    # Confirmed via testing: an element found via _find() can become invalid by the time
    # we act on it if the page transitions in between (e.g. password page -> OTP page) --
    # WinAppDriver returns a plain 500 Internal Error for this, not a distinguishable
    # "stale element" error. @retry re-finds the element each attempt (the whole method
    # body re-runs), which covers it -- see factory/retry.py.
    @retry(attempts=2, delay=0.5)
    def _click_once(self) -> None:
        self._find().click()

    def click(self) -> None:
        try:
            self._click_once()
        except Exception as exc:
            self._screenshot("click_FAILED")
            logger.error(f"click failed on {self.name!r}: {exc}")
            raise ComponentActionError(f"click failed on {self.name!r}: {exc}") from exc
        logger.success(f"click succeeded on {self.name!r}")
        self._screenshot("click")

    @retry(attempts=2, delay=0.5)
    def _click_at_center_once(self) -> None:
        self._find().click_at_center()

    def click_at_center(self) -> None:
        """Same as click(), but uses a real simulated mouse click at the element's
        center (WinAppDriverElement.click_at_center()) instead of the UIA Invoke
        pattern -- see that method's docstring for why. Use this when click() reports
        success but the on-screen control doesn't actually respond."""
        try:
            self._click_at_center_once()
        except Exception as exc:
            self._screenshot("click_at_center_FAILED")
            logger.error(f"click_at_center failed on {self.name!r}: {exc}")
            raise ComponentActionError(f"click_at_center failed on {self.name!r}: {exc}") from exc
        logger.success(f"click_at_center succeeded on {self.name!r}")
        self._screenshot("click_at_center")

    @retry(attempts=2, delay=0.5)
    def _type_once(self, text: str) -> None:
        self._find().send_keys(text)

    def type_text(self, text: str) -> None:
        try:
            self._type_once(text)
        except Exception as exc:
            self._screenshot("type_FAILED")
            logger.error(f"type failed on {self.name!r}: {exc}")
            raise ComponentActionError(f"type failed on {self.name!r}: {exc}") from exc
        logger.success(f"type succeeded on {self.name!r}")
        self._screenshot("type")

    @retry(attempts=2, delay=0.5)
    def _get_text_once(self) -> str:
        return self._find().get_text()

    def get_text(self, timeout: Optional[float] = None) -> str:
        original_timeout = self.timeout
        if timeout is not None:
            self.timeout = timeout
        try:
            text = self._get_text_once()
        except Exception as exc:
            logger.error(f"get_text failed on {self.name!r}: {exc}")
            raise
        finally:
            self.timeout = original_timeout
        logger.success(f"get_text succeeded on {self.name!r}: {text!r}")
        return text

    def exists(self, timeout: float = 2.0) -> bool:
        # Debug level, not success/error -- a "not found" result here is routinely the
        # expected outcome of a presence check used for branching (e.g. "is the email
        # step present or already skipped?"), not a failure worth flagging in color.
        original_timeout = self.timeout
        self.timeout = timeout
        try:
            self._find()
            found = True
        except TimeoutError:
            found = False
        finally:
            self.timeout = original_timeout
        logger.debug(f"exists check on {self.name!r} (timeout={timeout}s): {found}")
        return found

    def wait_until_gone(self, timeout: float, poll_interval: float = 0.5) -> bool:
        """True if the element becomes absent within timeout; False if it's still
        present when the timeout expires.

        NOT the same as exists(timeout) with a longer timeout -- confirmed via live
        testing this is a real, distinct bug, not just a naming confusion: exists()
        polls until the element is FOUND and returns as soon as that happens, so calling
        exists(timeout=15.0) right after an action that should make the element go away
        (e.g. clicking OTP Verify) can return True almost instantly if the element is
        still on screen for even a moment -- giving the page zero chance to actually
        transition away before being declared "still there, retry". This method instead
        polls until the element stops being found.
        """
        deadline = time.monotonic() + timeout
        while True:
            if not self.exists(timeout=poll_interval):
                return True
            if time.monotonic() >= deadline:
                return False
