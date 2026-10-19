"""Target-role sign-out popup (SignOutModal) -- actions only. Cancel exists in both the
waiting and the error view (and keeps the user signed in); Retry exists only in the
error view. See assertions/target/sign_out_modal.py's is_showing() and
is_error_showing().

Verified against source, not live: rebit TargetPc.UI
web/src/screens/onboarding/SignOutModal.tsx; resx keys Buttons_Cancel, Buttons_Retry.
"""

from components.base_component import BaseComponent
from locators.target.sign_out_modal import CANCEL_BUTTON_LOCATOR, RETRY_BUTTON_LOCATOR


class SignOutModal:
    def __init__(self, app_session):
        self._cancel_button = BaseComponent(app_session, *CANCEL_BUTTON_LOCATOR, "SignOutCancelButton")
        self._retry_button = BaseComponent(app_session, *RETRY_BUTTON_LOCATOR, "SignOutRetryButton")

    def click_cancel(self) -> None:
        self._cancel_button.click()

    def click_retry(self) -> None:
        self._retry_button.click()
