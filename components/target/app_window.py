"""The Target app's own native window chrome (title-bar close button) -- the OS
window frame itself, not a screen/dialog inside the app's own React/WebView2
content. Click action only, per explicit user direction (2026-10-14): once the full
transfer flow confirms migration is complete, close the app via this button rather
than leaving it open for Session.close()'s own process-kill cleanup to handle.
"""

from components.base_component import BaseComponent
from locators.target.app_window import CLOSE_BUTTON_LOCATOR


class AppWindow:
    def __init__(self, app_session):
        self._close_button = BaseComponent(app_session, *CLOSE_BUTTON_LOCATOR, "AppWindowCloseButton")

    def click_close(self) -> None:
        self._close_button.click()
