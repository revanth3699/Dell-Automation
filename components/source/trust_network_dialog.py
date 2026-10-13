"""Source PC's "Do you trust the <network> network?" dialog. Confirmed live (2026-10-07).
Mirrors components/target/common_dialogs.py's TrustNetworkDialog shape.

Per explicit user direction (2026-10-14): the existence check (is_showing()) moved out
to assertions/source/trust_network_dialog.py, called directly from flows/ -- this class
now holds only the click_yes_continue() action (previously accept(), which checked AND
clicked in one call).
"""

from components.base_component import BaseComponent
from locators.source.trust_network_dialog import YES_CONTINUE_BUTTON_LOCATOR


class TrustNetworkDialog:
    def __init__(self, app_session):
        self._yes_continue_button = BaseComponent(app_session, *YES_CONTINUE_BUTTON_LOCATOR, "YesContinueButton")

    def click_yes_continue(self) -> None:
        # Confirmed live (2026-10-07), same fix as the Target-side TrustNetworkDialog:
        # click() previously re-found the button with its full default timeout (10s)
        # even though the caller's is_showing() just confirmed the dialog's heading is
        # there. Short timeout here instead.
        self._yes_continue_button.click(timeout=2.0)
