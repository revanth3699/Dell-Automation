"""Reminder-confirmation panel ("Got it") -- actions only, no existence checks. See
assertions/target/reminder_confirmation_panel.py's is_showing().
"""

from components.base_component import BaseComponent
from locators.target.reminder_confirmation_panel import CLOSE_BUTTON_LOCATOR


class ReminderConfirmationPanel:
    def __init__(self, app_session):
        self._close_button = BaseComponent(app_session, *CLOSE_BUTTON_LOCATOR, "ReminderConfirmationCloseButton")

    def click_close(self) -> None:
        self._close_button.click()
