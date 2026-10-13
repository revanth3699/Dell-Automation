"""Expected heading text + locator + assertion function for
components.target.common_dialogs.CloseAppsDialog ("We need to close all other
applications"). Confirmed from a user-supplied screenshot (2026-10-06). Never a click
target, so it lives here rather than in locators/ -- per explicit user direction
(2026-10-14).
"""

from assertions.common import text_exists

HEADING_TEXT = "We need to close all other applications"
CLOSE_APPS_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, CLOSE_APPS_HEADING_LOCATOR, "CloseAppsHeading", timeout=timeout)
