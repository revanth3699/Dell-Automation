"""Expected heading text + locator + assertion function for the reminder-options panel
(shown in place of "Ready to get started?" after clicking "Remind me later." on the
Welcome-back screen -- see components.target.sign_in_screen.WelcomeBackScreen).

Confirmed from user-supplied screenshots (2026-10-19): heading "No rush—we'll remind
you", options "Tonight"/"Tomorrow"/"Next week", "Set reminder" button. Per CLAUDE.md's
gotcha: the real heading contains an apostrophe ("we'll") -- matching on a contains() of
the apostrophe-free "No rush" instead of the full string.
"""

from assertions.common import text_exists

HEADING_TEXT_SUBSTRING = "No rush"
REMINDER_OPTIONS_HEADING_LOCATOR = ("xpath", f'//*[contains(@Name, "{HEADING_TEXT_SUBSTRING}")]')


def is_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(session, REMINDER_OPTIONS_HEADING_LOCATOR, "ReminderOptionsHeading", timeout=timeout)
