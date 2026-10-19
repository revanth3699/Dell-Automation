"""Target-role Welcome screen secondary links (WelcomeMoveFilesCard) -- actions only:
"Remind me later." (opens the reminder picker --
components/target/welcome_deferral_screen.py) and "Sign out" (opens the sign-out popup
-- components/target/sign_out_modal.py). Deliberately a separate class from
components/target/sign_in_screen.py's WelcomeScreen/WelcomeBackScreen, which are not
modified. Presence checks: assertions/target/welcome_back_screen.py's is_showing() /
is_home_confirmed().

Verified against source, not live: rebit TargetPc.UI
web/src/screens/welcome/WelcomeMoveFilesCard.tsx; resx keys Buttons_RemindLater,
Buttons_SignOut.
"""

from components.base_component import BaseComponent
from locators.target.welcome_links import REMIND_ME_LATER_BUTTON_LOCATOR, SIGN_OUT_LINK_LOCATOR


class WelcomeLinks:
    def __init__(self, app_session):
        self._remind_me_later_button = BaseComponent(
            app_session, *REMIND_ME_LATER_BUTTON_LOCATOR, "RemindMeLaterButton"
        )
        self._sign_out_link = BaseComponent(app_session, *SIGN_OUT_LINK_LOCATOR, "SignOutLink")

    def click_remind_me_later(self) -> None:
        self._remind_me_later_button.click()

    def click_sign_out(self) -> None:
        self._sign_out_link.click()
