"""Expected heading text + locator + assertion function for
components.target.common_dialogs.InstallBrowsersToMigrateBookmarksDialog. Appears on
Target right after clicking the migrate button ("Bring everything over for me") when
the Source PC has a browser (e.g. Firefox) installed that this (Target) PC doesn't, so
that browser's bookmarks can't be migrated. Never a click target, so it lives here
rather than in locators/ -- per explicit user direction (2026-10-14).

Bug fixed here, confirmed via a user-supplied screenshot (2026-10-19): the heading
originally confirmed (2026-10-14), "Install one or more browsers to migrate your
bookmarks", does not match the live dialog -- the real heading is "Want to keep your
browser bookmarks?", with body text "It looks like you have bookmarks on your old PC.
To transfer them, install any browsers with bookmarks you'd like to keep: <browser
name(s)>. Resume after installing, or Skip to continue without transferring
bookmarks." Uses contains() on an apostrophe-free substring of the new heading (see
CLAUDE.md's Gotchas section on the apostrophe trap) rather than an exact match.
"""

from assertions.common import text_exists

HEADING_CONTAINS_TEXT = "Want to keep your browser bookmarks"
INSTALL_BROWSERS_HEADING_LOCATOR = ("xpath", f'//*[contains(@Name, "{HEADING_CONTAINS_TEXT}")]')


def is_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(
        session, INSTALL_BROWSERS_HEADING_LOCATOR, "InstallBrowsersToMigrateBookmarksHeading", timeout=timeout
    )
