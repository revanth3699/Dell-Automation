"""Expected heading text + locator + assertion function for
components.target.common_dialogs.InstallBrowsersToMigrateBookmarksDialog ("Install one
or more browsers to migrate your bookmarks"). Confirmed from a user-supplied
screenshot (2026-10-14): appears on Target right after clicking the migrate button
("Bring everything over for me") when the Source PC has a browser (e.g. Firefox)
installed that this (Target) PC doesn't, so that browser's bookmarks can't be
migrated. Never a click target, so it lives here rather than in locators/ -- per
explicit user direction (2026-10-14).
"""

from assertions.common import text_exists

HEADING_TEXT = "Install one or more browsers to migrate your bookmarks"
INSTALL_BROWSERS_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(
        session, INSTALL_BROWSERS_HEADING_LOCATOR, "InstallBrowsersToMigrateBookmarksHeading", timeout=timeout
    )
