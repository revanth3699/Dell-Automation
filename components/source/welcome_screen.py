"""Source PC's initial "Welcome to Dell Migrate." screen. Confirmed live (2026-10-06) via
Phase 0 spike against the real Source build. Source has no authentication step, so unlike
Target's WelcomeScreen, there's no sign-in-vs-already-signed-in branching here -- just
one real button to advance past this screen.

Per explicit user direction (2026-10-14): the existence check (is_showing()) moved out
to assertions/source/welcome_screen.py, called directly from flows/ -- this class now
holds only the click_get_started() action.
"""

from components.base_component import BaseComponent
from locators.source.welcome_screen import LETS_GET_STARTED_BUTTON_LOCATOR


class WelcomeScreen:
    def __init__(self, app_session):
        self._get_started_button = BaseComponent(
            app_session, *LETS_GET_STARTED_BUTTON_LOCATOR, "LetsGetStartedButton",
        )

    def click_get_started(self) -> None:
        self._get_started_button.click()
