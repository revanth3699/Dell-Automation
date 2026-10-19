"""Expected heading text + locator + assertion function for
components.target.pairing_code_entry_screen.ConfirmAccountsDialog -- shown only when
the two PCs' account names differ after a successful pairing code. Never a click
target, so it lives here rather than in locators/ -- per explicit user direction
(2026-10-14).

Bug fixed here (2026-10-19, first correction): a real run showed the dialog never
getting clicked -- repeated "ConfirmAccountsHeading: False" checks for the entire
preparing-files wait even though the account-mismatch dialog should have been on
screen. The heading originally confirmed from a user-supplied flow diagram
(dell screens flow.pdf, 2026-10-05), "Let's make sure we're connecting the right user
accounts", was assumed to be an apostrophe-mismatch problem (two apostrophes, "Let's"
and "we're", hitting this project's documented curly-vs-straight-apostrophe trap -- see
CLAUDE.md's Gotchas section) and was switched to a contains() match. That fix did not
work either.

Bug fixed here (2026-10-19, second correction, confirmed via an actual live
screenshot of a real run -- not the reference diagram): the real heading is "Your user
account names don't match", an entirely different phrase from what every previous
version of this file assumed -- not just an apostrophe variant of it. Body text: "The
names of the user accounts on your PCs aren't the same. You can continue with these
accounts, or cancel the transfer and sign in again with matching accounts.", followed by
"User account on this PC: <name>" / "User account on other PC: <name>", and two buttons,
"Cancel transfer" and "Continue" (the existing CONFIRM_ACCOUNTS_CONTINUE_BUTTON_LOCATOR
in locators/target/confirm_accounts_dialog.py already targets "Continue" generically and
needs no change). Uses contains() on an apostrophe-free substring ("don't match" has its
own apostrophe) rather than an exact match, same reasoning as every other
apostrophe-containing heading in this project.
"""

from assertions.common import text_exists

# Apostrophe-free substring of "Your user account names don't match" -- avoids the
# exact-match apostrophe-mismatch trap (see module docstring above).
HEADING_CONTAINS_TEXT = "Your user account names"
CONFIRM_ACCOUNTS_HEADING_LOCATOR = ("xpath", f'//*[contains(@Name, "{HEADING_CONTAINS_TEXT}")]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, CONFIRM_ACCOUNTS_HEADING_LOCATOR, "ConfirmAccountsHeading", timeout=timeout)
