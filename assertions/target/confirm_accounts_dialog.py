"""Expected heading text + locator + assertion function for
components.target.pairing_code_entry_screen.ConfirmAccountsDialog ("Let's make sure
we're connecting the right user accounts" -- shown only when the two PCs' account
names differ after a successful pairing code). Originally confirmed only from a
user-supplied flow diagram (dell screens flow.pdf, 2026-10-05); confirmed live
(2026-10-15) via a real run's screenshot + log -- heading matched exactly, the dialog
appeared during the preparing-files wait (two account names shown: "Revanth Bashyam"
vs "Betsol"), and is_showing()/click_continue() both worked correctly. Never a click
target, so it lives here rather than in locators/ -- per explicit user direction
(2026-10-14).

Bug fixed here, confirmed via a live run (2026-10-19): a real run showed the dialog
never getting clicked -- repeated "ConfirmAccountsHeading: False" checks for the
entire preparing-files wait even though the account-mismatch dialog should have been
on screen. The original locator did an exact @Name="Let's make sure we're connecting
the right user accounts" match -- this phrase has TWO apostrophes ("Let's", "we're"),
hitting this project's own documented curly-vs-straight-apostrophe trap (see CLAUDE.md's
Gotchas section and assertions/source/regional_settings_not_supported_dialog.py's
history), so is_showing() could return False forever regardless of timeout. Replaced
with contains() on an apostrophe-free, distinctive substring, same fix pattern as every
other apostrophe-containing heading in this project.
"""

from assertions.common import text_exists

# Apostrophe-free substring of "Let's make sure we're connecting the right user
# accounts" -- avoids the exact-match apostrophe-mismatch trap (see module docstring
# above).
HEADING_CONTAINS_TEXT = "connecting the right user accounts"
CONFIRM_ACCOUNTS_HEADING_LOCATOR = ("xpath", f'//*[contains(@Name, "{HEADING_CONTAINS_TEXT}")]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, CONFIRM_ACCOUNTS_HEADING_LOCATOR, "ConfirmAccountsHeading", timeout=timeout)
