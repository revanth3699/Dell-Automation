"""Reminder-options panel (Tonight/Tomorrow/Next week) -- actions only, no existence
checks. See assertions/target/reminder_options_screen.py's is_showing().
"""

from components.base_component import BaseComponent
from locators.target.reminder_options_screen import (
    NEXT_WEEK_OPTION_LOCATOR,
    SET_REMINDER_BUTTON_LOCATOR,
    TOMORROW_OPTION_LOCATOR,
    TONIGHT_OPTION_LOCATOR,
)

_OPTION_LOCATORS = {
    "tonight": TONIGHT_OPTION_LOCATOR,
    "tomorrow": TOMORROW_OPTION_LOCATOR,
    "next_week": NEXT_WEEK_OPTION_LOCATOR,
}


class ReminderOptionsScreen:
    def __init__(self, app_session):
        self._app_session = app_session
        self._set_reminder_button = BaseComponent(app_session, *SET_REMINDER_BUTTON_LOCATOR, "SetReminderButton")

    def select_option(self, option: str) -> None:
        locator = _OPTION_LOCATORS.get(option)
        if locator is None:
            raise ValueError(f"Unknown reminder option {option!r} -- expected one of {sorted(_OPTION_LOCATORS)}")
        BaseComponent(self._app_session, *locator, f"Reminder{option.title().replace('_', '')}Option").click()

    def click_set_reminder(self) -> None:
        self._set_reminder_button.click()
