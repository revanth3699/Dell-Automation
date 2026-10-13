"""Expected heading text + locator + assertion function for
components.target.common_dialogs.DesktopShortcutDialog ("Add a desktop shortcut before
you go"). Confirmed from a user-supplied screenshot (2026-10-13). Never a click target,
so it lives here rather than in locators/ -- per explicit user direction (2026-10-14).
"""

from assertions.common import text_exists

HEADING_TEXT = "Add a desktop shortcut before you go"
DESKTOP_SHORTCUT_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(session, DESKTOP_SHORTCUT_HEADING_LOCATOR, "DesktopShortcutHeading", timeout=timeout)
