"""Locators for components.target.common_dialogs.CloseAppsDialog -- click-target
locator only. The heading assertion locator lives in
assertions/target/close_apps_dialog.py instead.

Bug fixed here, confirmed via a user-supplied screenshot (2026-10-19): the button is
actually named "Close applications" (plural), not "Close Application" -- the real
dialog, "Close other applications", has a "Cancel transfer" and a "Close applications"
button.
"""

CLOSE_APPLICATION_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Close applications"]')

# Added 2026-10-19 (verified against rebit source, not live). CloseApplicationsModel.tsx:
# first-attempt footer is Cancel transfer (Buttons_CancelTransfer, secondary) + Close
# applications (primary); after a failed close (hasFailedAttempt) the footer becomes
# Check again (Buttons_CheckAgain, primary) + Retry (secondary -- the C# constant
# CloseApplicationsPageViewModel.RetryPrompt = "Retry", sent as state.primaryButtonText).
# All three render through PopUpModelFooter's DDSButton, hence //Button.
RETRY_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Retry"]')
CHECK_AGAIN_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Check again"]')
CANCEL_TRANSFER_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Cancel transfer"]')
