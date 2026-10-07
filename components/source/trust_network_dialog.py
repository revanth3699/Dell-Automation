"""Source PC's "Do you trust the <network> network?" dialog. Confirmed live (2026-10-07).
Mirrors components/target/common_dialogs.py's TrustNetworkDialog shape.
"""

from components.base_component import BaseComponent
from locators.source.trust_network_dialog import HEADING_LOCATOR, YES_CONTINUE_BUTTON_LOCATOR


class TrustNetworkDialog:
    def __init__(self, app_session):
        self._heading = BaseComponent(app_session, *HEADING_LOCATOR, "TrustNetworkHeading")
        self._yes_continue_button = BaseComponent(app_session, *YES_CONTINUE_BUTTON_LOCATOR, "YesContinueButton")

    def is_showing(self, timeout: float = 2.0) -> bool:
        return self._heading.exists(timeout=timeout)

    def accept(self, timeout: float = 2.0) -> bool:
        """Clicks "Yes, continue" if the dialog is showing. Returns whether it was
        present at all, so callers can distinguish "already past this dialog" from
        "accepted it just now" without a separate is_showing() call.

        Confirmed live (2026-10-07), same fix as the Target-side TrustNetworkDialog:
        click() previously re-found the button with its full default timeout (10s)
        even though exists() just confirmed the dialog's heading is there. Passes a
        short timeout here instead.
        """
        if not self._heading.exists(timeout=timeout):
            return False
        self._yes_continue_button.click(timeout=2.0)
        return True
