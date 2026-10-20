"""Target-role "Got it" reminder-set confirmation (WelcomeFamilyStage, mode 'success')
-- actions only: Close. See assertions/target/deferral_success_screen.py's is_showing().

Verified against source, not live: rebit TargetPc.UI
web/src/screens/welcome/WelcomeFamilyStage.tsx (ReminderSuccess); resx key Buttons_Close.
"""

from components.base_component import BaseComponent
from locators.target.deferral_success_screen import CLOSE_BUTTON_LOCATOR


class DeferralSuccessScreen:
    def __init__(self, app_session):
        self._close_button = BaseComponent(app_session, *CLOSE_BUTTON_LOCATOR, "DeferralSuccessCloseButton")

    def click_close(self) -> None:
        self._close_button.click()
