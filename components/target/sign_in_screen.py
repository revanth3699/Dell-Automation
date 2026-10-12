"""
Target PC pre-auth app-side screens (Target-only: Source PC has no authentication step):
the initial "Welcome to Dell" sign-in screen, and the "Welcome back, <name>" screen shown
instead when the app silently refreshes a cached login. Confirmed locators in
tools/phase0_inspection_notes.md (Welcome screen) and via a user-supplied screenshot,
2026-10-05 (Welcome-back screen).
"""

from components.base_component import BaseComponent
from locators.target.welcome_screen import SIGN_IN_BUTTON_LOCATOR
from locators.target.welcome_back_screen import (
    GET_STARTED_BUTTON_LOCATOR,
    SIGN_OUT_BUTTON_LOCATOR,
    WELCOME_BACK_HEADING_LOCATOR,
)


class WelcomeScreen:
    """Initial, not-yet-signed-in "Welcome to Dell" screen."""

    def __init__(self, app_session):
        self._sign_in_button = BaseComponent(app_session, *SIGN_IN_BUTTON_LOCATOR, "SignInButton")

    def is_showing(self, timeout: float = 1.0) -> bool:
        return self._sign_in_button.exists(timeout=timeout)

    def click_sign_in(self) -> None:
        self._sign_in_button.click()


class WelcomeBackScreen:
    """Confirmed via a user-supplied screenshot (2026-10-05): shown instead of
    WelcomeScreen when the app's own TrySilentLoginAsync silently refreshes a cached
    OIDC token on launch. Unlike the trust-network/pairing-discovery already-signed-in
    shortcuts (see components/shared/common_dialogs.py and
    components/target/pairing_discovery_screen.py), this screen is a real step -- its
    own blue circular "get started" button must still be clicked to proceed, confirmed
    directly by the user.
    """

    def __init__(self, app_session):
        self._heading = BaseComponent(app_session, *WELCOME_BACK_HEADING_LOCATOR, "WelcomeBackHeading")
        self._get_started_button = BaseComponent(app_session, *GET_STARTED_BUTTON_LOCATOR, "GetStartedButton")
        self._sign_out_button = BaseComponent(app_session, *SIGN_OUT_BUTTON_LOCATOR, "SignOutButton")

    def is_showing(self, timeout: float = 1.0) -> bool:
        return self._heading.exists(timeout=timeout)

    def click_get_started(self) -> None:
        self._get_started_button.click()

    def is_home_confirmed(self, timeout: float = 2.0) -> bool:
        """Confirms we're genuinely back on this screen post-migration (after
        MigrationCompleteScreen.click_back_to_home()), via the "Sign Out" button --
        distinct from is_showing()'s heading-only check, which this screen's own
        original already-signed-in-shortcut use (SignInFlow) doesn't need.

        Bug fixed here, confirmed directly by the user via a live run (2026-10-13):
        this used to check for the "Nothing's lost from your old PC" bullet text,
        which timed out (never found within 30s) on a real post-migration run --
        replaced with the "Sign Out" button, confirmed visible on this screen via a
        user-supplied screenshot.
        """
        return self._sign_out_button.exists(timeout=timeout)
