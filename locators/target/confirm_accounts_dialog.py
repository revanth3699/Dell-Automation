"""Locators for components.target.pairing_code_entry_screen.ConfirmAccountsDialog --
click-target locator only. The heading assertion locator lives in
assertions/target/confirm_accounts_dialog.py instead.
"""

# Shared with locators/target/welcome_screen.py and welcome_back_screen.py -- same
# convention there: each component only reads this locator while its own screen is
# confirmed showing via is_showing() first, so reusing the generic "Continue" text
# across different screens/components is safe (only one such button exists on screen at
# a time).
CONFIRM_ACCOUNTS_CONTINUE_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Continue"]')

# Added 2026-10-19 (verified against rebit source, not live): AccountMismatchModal.tsx's
# PopUpModelFooter secondaryLabel is Buttons_CancelTransfer ("Cancel transfer"), a DDSButton.
CANCEL_TRANSFER_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Cancel transfer"]')
