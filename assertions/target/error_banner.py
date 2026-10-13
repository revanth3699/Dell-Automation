"""Expected error-banner text + locator + assertion function for the Target PC browser
sign-in steps (email, password, OTP) -- confirmed from a user-supplied flow diagram
(dell screens flow.pdf, 2026-10-05), not yet independently confirmed live. Never a
click target, so it lives here rather than in locators/ -- per explicit user direction
(2026-10-14).

All three steps' full error text shares this prefix; password/OTP each append their own
account-lockout warning. Matches on the common prefix via contains() rather than each
step's full text, so it stays robust to the per-step detail changing independently.
"""

from assertions.common import text_exists

COMMON_PREFIX = "We are unable to match the details you entered with our records"

EMAIL_ERROR_TEXT = COMMON_PREFIX

PASSWORD_ERROR_TEXT = (
    COMMON_PREFIX
    + ". Your account will be locked if an incorrect password is entered 6 times. "
    "Please click the 'Create or Reset password' link if you would like to reset "
    "your password."
)

OTP_ERROR_TEXT = COMMON_PREFIX + ". Your account will be locked in case of 6 incorrect attempts."

ERROR_BANNER_LOCATOR = ("xpath", f'//*[contains(@Name, "{COMMON_PREFIX}")]')


def is_showing(session, timeout: float = 8.0) -> bool:
    return text_exists(session, ERROR_BANNER_LOCATOR, "ErrorBanner", timeout=timeout)
