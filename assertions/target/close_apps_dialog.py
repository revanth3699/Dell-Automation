"""Expected heading text + locator + assertion function for
components.target.common_dialogs.CloseAppsDialog. Never a click target, so it lives
here rather than in locators/ -- per explicit user direction (2026-10-14).

Bug fixed here, confirmed via a live run + a user-supplied screenshot (2026-10-19): the
heading originally assumed from a 2026-10-06 screenshot, "We need to close all other
applications", does not match the live app -- the real heading is "Close other
applications", with body text "Some applications are still running and could interrupt
your transfer. Save any work you'd like to keep, then close these applications to
continue:" followed by the app name(s) (e.g. "Microsoft Edge") and two buttons,
"Cancel transfer" and "Close applications" (see
locators/target/close_apps_dialog.py's own correction). A real run confirmed the
practical impact: this dialog sat blocking "Migrate now" undetected for the entire
RECLICK_INTERVAL_SECONDS window, the re-click then timed out against a covered button,
and the flow crashed with "Could not find the 'Bring everything over for me' / 'Migrate
now' button" instead of ever clicking through the dialog that was actually in the way.
Uses contains() rather than an exact match for consistency with every other corrected
heading in this project, even though this particular heading happens to have no
apostrophe itself.
"""

from assertions.common import text_exists

HEADING_CONTAINS_TEXT = "Close other applications"
CLOSE_APPS_HEADING_LOCATOR = ("xpath", f'//*[contains(@Name, "{HEADING_CONTAINS_TEXT}")]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, CLOSE_APPS_HEADING_LOCATOR, "CloseAppsHeading", timeout=timeout)
