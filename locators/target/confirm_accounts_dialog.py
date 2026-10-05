"""Locators for components.target.pairing_code_entry_screen.ConfirmAccountsDialog
("Let's make sure we're connecting the right user accounts" -- shown only when the two
PCs' account names differ after a successful pairing code). Confirmed from a
user-supplied flow diagram (dell screens flow.pdf, 2026-10-05), not yet independently
confirmed live.
"""

CONFIRM_ACCOUNTS_HEADING_LOCATOR = (
    "xpath",
    '//*[@Name="Let\'s make sure we\'re connecting the right user accounts"]',
)
# Shared with locators/target/welcome_screen.py and welcome_back_screen.py -- same
# convention there: each component only reads this locator while its own screen is
# confirmed showing via is_showing() first, so reusing the generic "Continue" text
# across different screens/components is safe (only one such button exists on screen at
# a time).
CONFIRM_ACCOUNTS_CONTINUE_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Continue"]')
