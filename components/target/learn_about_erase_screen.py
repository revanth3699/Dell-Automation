"""Target-role "Ready to erase your old PC?" screen (LearnAboutEraseView) -- actions
only. "Back to Home" sends Migration.Stop and restarts at the home screen (per
LearnAboutEraseView.tsx's header comment). See
assertions/target/learn_about_erase_screen.py's is_showing().

Verified against source, not live: rebit TargetPc.UI
web/src/screens/results/LearnAboutEraseView.tsx + components/stage/StageCard.tsx; resx
key Buttons_BackToHome.
"""

from components.base_component import BaseComponent
from locators.target.learn_about_erase_screen import BACK_TO_HOME_BUTTON_LOCATOR


class LearnAboutEraseScreen:
    def __init__(self, app_session):
        self._back_to_home_button = BaseComponent(app_session, *BACK_TO_HOME_BUTTON_LOCATOR, "BackToHomeButton")

    def click_back_to_home(self) -> None:
        self._back_to_home_button.click()
