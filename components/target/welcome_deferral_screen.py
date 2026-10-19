"""Target-role "No rush" reminder picker (WelcomeFamilyStage, mode 'picker'), shown in
the Welcome screen's right card after "Remind me later." -- actions only: choose
Tonight / Tomorrow / Next week, Set reminder, or Close. See
assertions/target/welcome_deferral_screen.py's is_showing().

Verified against source, not live: rebit TargetPc.UI
web/src/screens/welcome/WelcomeFamilyStage.tsx (ReminderPicker); resx keys
WelcomeDeferral_OptionTonight/Tomorrow/NextWeek, Buttons_SetReminder, Buttons_Close.
"""

from components.base_component import BaseComponent
from locators.target.welcome_deferral_screen import (
    CLOSE_BUTTON_LOCATOR,
    REMINDER_OPTION_LABELS,
    SET_REMINDER_BUTTON_LOCATOR,
    reminder_option_locator,
)


class WelcomeDeferralScreen:
    def __init__(self, app_session):
        self._session = app_session
        self._set_reminder_button = BaseComponent(app_session, *SET_REMINDER_BUTTON_LOCATOR, "SetReminderButton")
        self._close_button = BaseComponent(app_session, *CLOSE_BUTTON_LOCATOR, "WelcomeDeferralCloseButton")

    def select_option(self, option: str) -> None:
        """`option` is one of REMINDER_OPTION_LABELS' keys ("tonight", "tomorrow",
        "next_week") or the visible label text."""
        if option not in REMINDER_OPTION_LABELS and option not in REMINDER_OPTION_LABELS.values():
            raise ValueError(f"unknown reminder option {option!r}; expected one of {sorted(REMINDER_OPTION_LABELS)}")
        radio = BaseComponent(self._session, *reminder_option_locator(option), f"ReminderOption_{option}")
        radio.click()

    def click_set_reminder(self) -> None:
        self._set_reminder_button.click()

    def click_close(self) -> None:
        self._close_button.click()
