"""Target-role "We couldn't schedule your reminder" error card (WelcomeFamilyStage,
mode 'error') -- actions only: Close. See
assertions/target/welcome_deferral_error_screen.py's is_showing().

Verified against source, not live: rebit TargetPc.UI
web/src/screens/welcome/WelcomeFamilyStage.tsx (ReminderErrorCard); resx key
Buttons_Close.
"""

from components.base_component import BaseComponent
from locators.target.welcome_deferral_error_screen import CLOSE_BUTTON_LOCATOR


class WelcomeDeferralErrorScreen:
    def __init__(self, app_session):
        self._close_button = BaseComponent(app_session, *CLOSE_BUTTON_LOCATOR, "WelcomeDeferralErrorCloseButton")

    def click_close(self) -> None:
        self._close_button.click()
