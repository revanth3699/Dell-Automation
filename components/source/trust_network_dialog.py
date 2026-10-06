"""Source PC's "Do you trust the <network> network?" dialog. Confirmed from a
user-supplied screenshot (2026-10-06) -- NOT yet confirmed live (didn't appear in the one
live run done so far, likely conditional on whether this network was already trusted).
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
        "accepted it just now" without a separate is_showing() call."""
        if not self._heading.exists(timeout=timeout):
            return False
        self._yes_continue_button.click()
        return True
