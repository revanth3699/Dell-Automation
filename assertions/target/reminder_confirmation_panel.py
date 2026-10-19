"""Expected heading text + locator + assertion function for the reminder-confirmation
panel (shown after clicking "Set reminder" -- green thumbs-up "Got it" heading, body
"We'll send you a notification {option} to transfer what you want to keep."). Confirmed
from a user-supplied screenshot (2026-10-19). Never a click target, so it lives here
rather than in locators/.
"""

from assertions.common import text_exists

HEADING_TEXT = "Got it"
REMINDER_CONFIRMATION_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(session, REMINDER_CONFIRMATION_HEADING_LOCATOR, "ReminderConfirmationHeading", timeout=timeout)
