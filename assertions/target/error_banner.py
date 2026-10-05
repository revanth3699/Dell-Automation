"""Expected error-banner text for the Target PC browser sign-in steps (email, password,
OTP) -- confirmed from a user-supplied flow diagram (dell screens flow.pdf, 2026-10-05),
not yet independently confirmed live. Centralized here so the shared locator
(locators/target/error_banner.py) and any caller that wants to assert on this text both
read from one place instead of duplicating the string.

All three share this prefix; password/OTP each append their own account-lockout warning.
"""

COMMON_PREFIX = "We are unable to match the details you entered with our records"

EMAIL_ERROR_TEXT = COMMON_PREFIX

PASSWORD_ERROR_TEXT = (
    COMMON_PREFIX
    + ". Your account will be locked if an incorrect password is entered 6 times. "
    "Please click the 'Create or Reset password' link if you would like to reset "
    "your password."
)

OTP_ERROR_TEXT = COMMON_PREFIX + ". Your account will be locked in case of 6 incorrect attempts."
