"""Expected heading text + locator + assertion function for
components.source.confirm_cancel_dialog.ConfirmCancelDialog ("Are you sure you want to
cancel?" -- "You can always use your desktop shortcut to come back later.").

Confirmed via a user-supplied screenshot (2026-10-13): clicking Cancel on
BatteryCriticallyLowDialog does NOT just dismiss that dialog -- it triggers THIS
confirmation instead, asking whether to cancel the whole migration. The point of
cancelling the battery warning is to keep the run going, not abort it, so this is
dismissed with "No, don't cancel" wherever BatteryCriticallyLowDialog.click_cancel()
is called (see flows/source/pairing_flow.py and flows/source/transfer_flow.py).

Never a click target, so it lives here rather than in locators/ -- per explicit user
direction (2026-10-14).
"""

from assertions.common import text_exists

HEADING_TEXT = "Are you sure you want to cancel?"
CONFIRM_CANCEL_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, CONFIRM_CANCEL_HEADING_LOCATOR, "ConfirmCancelHeading", timeout=timeout)
