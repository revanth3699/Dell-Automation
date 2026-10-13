"""Expected text + locators + assertion functions for
components.target.sign_in_screen.WelcomeBackScreen ("Welcome back, <name>" screen shown
when the app silently refreshes a cached login). Confirmed via a user-supplied
screenshot, 2026-10-05. Neither locator here is ever a click target, so both live here
rather than in locators/ -- per explicit user direction (2026-10-14).

SIGN_OUT_TEXT: confirmed directly by the user via a live run (2026-10-13): the
"Nothing's lost from your old PC" bullet text this used to check for timed out on a
real post-migration run -- replaced with the "Sign Out" button/link as the real
confirmation that we're genuinely back on the home screen post-migration.
"""

from assertions.common import text_exists

WELCOME_BACK_CONTAINS_TEXT = "Welcome back"
SIGN_OUT_TEXT = "Sign Out"

WELCOME_BACK_HEADING_LOCATOR = ("xpath", f'//*[contains(@Name, "{WELCOME_BACK_CONTAINS_TEXT}")]')
SIGN_OUT_BUTTON_LOCATOR = ("xpath", f'//*[@Name="{SIGN_OUT_TEXT}"]')


def is_showing(session, timeout: float = 1.0) -> bool:
    return text_exists(session, WELCOME_BACK_HEADING_LOCATOR, "WelcomeBackHeading", timeout=timeout)


def is_home_confirmed(session, timeout: float = 2.0) -> bool:
    """Confirms we're genuinely back on this screen post-migration, via the "Sign Out"
    button -- distinct from is_showing()'s heading-only check, which this screen's own
    original already-signed-in-shortcut use (SignInFlow) doesn't need."""
    return text_exists(session, SIGN_OUT_BUTTON_LOCATOR, "SignOutButton", timeout=timeout)
