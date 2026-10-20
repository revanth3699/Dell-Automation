"""Locators for components.target.welcome_deferral_screen.WelcomeDeferralScreen --
click-target locators only. The heading assertion locator lives in
assertions/target/welcome_deferral_screen.py instead.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/welcome/WelcomeFamilyStage.tsx, ReminderPicker (Resources/Resources.resx):
- REMINDER_OPTION_LABELS / reminder_option_locator(): the options are native
  <input type="radio"> elements each wrapped in a <label> whose text is
  t(option.labelKey) -- WelcomeDeferral_OptionTonight = "Tonight",
  WelcomeDeferral_OptionTomorrow = "Tomorrow", WelcomeDeferral_OptionNextWeek =
  "Next week" (constants/reminderOptions.ts maps the wire tokens tonight / tomorrow /
  nextWeek to those keys). A wrapping <label> gives the radio that accessible Name, so
  each is a RadioButton control named by its label.
- SET_REMINDER_BUTTON_LOCATOR: a plain <button> labelled t('Buttons_SetReminder') =
  "Set reminder" (disabled until an option is selected).
- CLOSE_BUTTON_LOCATOR: a plain <button> labelled t('Buttons_Close') = "Close" plus an
  aria-hidden close-x icon. Excludes AutomationId="CloseButton" so it can never match
  the app's native title-bar close button instead (same reasoning as
  locators/target/regional_settings_not_supported_dialog.py). The deferral-success and
  deferral-error cards render the same Close button, so their locator modules import
  this one rather than duplicating it.
"""

REMINDER_OPTION_LABELS = {
    "tonight": "Tonight",
    "tomorrow": "Tomorrow",
    "next_week": "Next week",
}

SET_REMINDER_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Set reminder"]')
CLOSE_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Close" and not(@AutomationId="CloseButton")]')


def reminder_option_locator(option: str) -> tuple:
    """Locator for one reminder radio. `option` is a REMINDER_OPTION_LABELS key
    ("tonight", "tomorrow", "next_week") or the visible label itself."""
    label = REMINDER_OPTION_LABELS.get(option, option)
    return ("xpath", f'//RadioButton[@Name="{label}"]')
