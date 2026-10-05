"""Locator for the error banner shared by EmailStep/PasswordStep/OtpStep (see
components.target.browser_sign_in_page). Matches on the common prefix via contains()
rather than each step's full text, so it stays robust to the per-step detail (e.g. the
password/OTP account-lockout warning) changing independently. The expected text itself is
centralized in assertions/target/error_banner.py -- imported from there, not duplicated
here, so there's exactly one copy of this string in the codebase.
"""

from assertions.target.error_banner import COMMON_PREFIX

ERROR_BANNER_LOCATOR = ("xpath", f'//*[contains(@Name, "{COMMON_PREFIX}")]')
