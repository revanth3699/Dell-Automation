"""Expected heading text + locator + assertion function for
components.target.pairing_code_entry_screen.ConfirmAccountsDialog ("Let's make sure
we're connecting the right user accounts" -- shown only when the two PCs' account
names differ after a successful pairing code). Confirmed from a user-supplied flow
diagram (dell screens flow.pdf, 2026-10-05), not yet independently confirmed live.
Never a click target, so it lives here rather than in locators/ -- per explicit user
direction (2026-10-14).
"""

from assertions.common import text_exists

HEADING_TEXT = "Let's make sure we're connecting the right user accounts"
CONFIRM_ACCOUNTS_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, CONFIRM_ACCOUNTS_HEADING_LOCATOR, "ConfirmAccountsHeading", timeout=timeout)
