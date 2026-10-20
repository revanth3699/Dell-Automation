"""Expected heading text + locator + assertion function for
components.target.common_dialogs.SignInWaitingModal ("Sign in to MyDell to continue" /
"Waiting for sign-in..." modal). Heading text confirmed from the project's original
reference walkthrough. Never a click target, so it lives here rather than in locators/
-- per explicit user direction (2026-10-14).
"""

from assertions.common import text_exists

HEADING_TEXT = "Sign in to your Dell account"
SIGN_IN_WAITING_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, SIGN_IN_WAITING_HEADING_LOCATOR, "SignInWaitingHeading", timeout=timeout)
