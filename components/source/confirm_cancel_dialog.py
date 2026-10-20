"""Source PC's "Are you sure you want to cancel?" dialog -- shown after clicking
Cancel on BatteryCriticallyLowDialog. See
assertions/source/confirm_cancel_dialog.py's is_showing() for why this needs handling
at all.
"""

from components.base_component import BaseComponent
from locators.source.confirm_cancel_dialog import NO_DONT_CANCEL_BUTTON_LOCATOR, YES_CANCEL_NOW_BUTTON_LOCATOR


class ConfirmCancelDialog:
    def __init__(self, app_session):
        self._no_dont_cancel_button = BaseComponent(
            app_session, *NO_DONT_CANCEL_BUTTON_LOCATOR, "ConfirmCancelNoDontCancelButton"
        )
        self._yes_cancel_now_button = BaseComponent(
            app_session, *YES_CANCEL_NOW_BUTTON_LOCATOR, "ConfirmCancelYesCancelNowButton"
        )

    def click_no_dont_cancel(self) -> None:
        self._no_dont_cancel_button.click()

    def click_yes_cancel_now(self) -> None:
        """Confirms the cancel -- only the state-machine "old PC cancels" scenarios use
        this (2026-10-19, verified against source, not live)."""
        self._yes_cancel_now_button.click()
