"""Expected heading texts + locators + assertion functions for
components.target.sign_out_modal.SignOutModal -- the popup shown for the whole span of a
sign-out attempt (opened by the Welcome screen's "Sign out" link).

Verified against source, not live: rebit TargetPc.UI
web/src/screens/onboarding/SignOutModal.tsx has two views keyed on state.errorMessage:
- waiting: PopUpModel titled t('SignOut_Title') = "We’re signing you out of your Dell
  account" (Resources/Resources.resx) -- curly apostrophe in "We’re", so matched on the
  apostrophe-free substring "signing you out" via contains().
- error: PopUpModel titled t('SignOutError_Title') = "There was a problem signing out"
  -- apostrophe-free, matched exactly.
Neither is ever a click target, so both live here.
"""

from assertions.common import text_exists

HEADING_CONTAINS_TEXT = "signing you out"
SIGN_OUT_HEADING_LOCATOR = ("xpath", f'//*[contains(@Name, "{HEADING_CONTAINS_TEXT}")]')

ERROR_HEADING_TEXT = "There was a problem signing out"
SIGN_OUT_ERROR_HEADING_LOCATOR = ("xpath", f'//*[@Name="{ERROR_HEADING_TEXT}"]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, SIGN_OUT_HEADING_LOCATOR, "SignOutHeading", timeout=timeout)


def is_error_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, SIGN_OUT_ERROR_HEADING_LOCATOR, "SignOutErrorHeading", timeout=timeout)
