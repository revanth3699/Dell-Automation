"""Assertion function for components.target.browser_sign_in_page.RestorePagesDialog
(Chrome's "Chrome didn't shut down correctly" restore-pages dialog).
RESTORE_PAGES_CLOSE_BUTTON_LOCATOR itself stays in
locators/target/restore_pages_dialog.py -- it's a genuine click target
(click_close() uses it directly), not a pure assertion locator -- this just builds the
poll+assert check around it using the common assertions/common.py methods.
"""

from assertions.common import button_exists
from locators.target.restore_pages_dialog import RESTORE_PAGES_CLOSE_BUTTON_LOCATOR


def is_showing(session, timeout: float = 1.5) -> bool:
    return button_exists(session, RESTORE_PAGES_CLOSE_BUTTON_LOCATOR, "RestorePagesCloseButton", timeout=timeout)
