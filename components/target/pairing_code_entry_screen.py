"""
Target-side pairing-code screens, shown once Source PC is found (i.e. once the
pairing-discovery screen's "We're looking for your other PC" heading clears -- see
assertions/target/pairing_discovery_screen.py). Confirmed from a user-supplied flow
diagram (dell screens flow.pdf, 2026-10-05), not yet independently confirmed live.

PairingCodeEntryScreen's heading text and ConfirmAccountsDialog's heading/button text are
taken directly from that diagram's screenshots and are solid. The 6 individual code-entry
boxes' exact accessible names are NOT confirmed -- no live DOM access yet, and unlike the
browser-side OTP boxes (components/target/browser_sign_in_page.py's "Verify Passcode
One".."Six", a web-page-specific accessibility hint), this is a different, app-side
WPF/WinUI control tree with no confirmed equivalent naming. enter_code() below finds boxes
positionally (first N Edit controls under the heading) rather than guessing specific
names. Confirm/adjust once hit for real.

The reference diagram also shows no visible submit button under the 6 boxes, consistent
with an auto-submit-once-all-digits-entered pattern (the same product convention the
browser-side OTP step already uses elsewhere in this app) -- if a submit button DOES turn
out to be required once this runs live, add an explicit click to enter_code().

Per explicit user direction (2026-10-14): existence checks (is_showing()/
wait_until_showing()/wait_until_gone() on PairingCodeEntryScreen, is_showing() on
ConfirmAccountsDialog) moved out to assertions/target/pairing_code_entry_screen.py and
assertions/target/confirm_accounts_dialog.py, called directly from flows/ -- these
classes now hold only actions. ConfirmAccountsDialog.accept() (which used to check AND
click in one call) is now click_continue(), a pure action -- callers check
is_showing() first.
"""

from components.base_component import BaseComponent, ComponentActionError
from utils.wait_utils import poll_until
from locators.target.confirm_accounts_dialog import CONFIRM_ACCOUNTS_CONTINUE_BUTTON_LOCATOR


class PairingCodeEntryScreen:
    """"Let's connect your two PCs" -- enter the verification code shown on Source PC."""

    def __init__(self, app_session):
        self._session = app_session

    def enter_code(self, code: str, box_count: int = 6, timeout: float = 10.0) -> None:
        """Types one digit per box into the first `box_count` Edit controls found on the
        page, in order. See module docstring -- box locators are positional, not
        name-based, since the individual boxes' accessible names aren't confirmed yet.
        """
        def _find_boxes():
            boxes = self._session.find_elements("xpath", "//Edit")
            return boxes if len(boxes) >= box_count else None

        boxes = poll_until(_find_boxes, timeout=timeout, interval=0.5)
        if boxes is None:
            raise ComponentActionError(
                f"PairingCodeEntryScreen.enter_code: could not find {box_count} code-entry "
                f"boxes within {timeout}s"
            )
        for digit, box in zip(code, boxes):
            box.send_keys(digit)


class ConfirmAccountsDialog:
    """"Let's make sure we're connecting the right user accounts" -- shown only when the
    two PCs' user account names differ (confirmed from the reference diagram) after a
    successful pairing code. Not every pairing shows this; callers should check
    assertions.target.confirm_accounts_dialog.is_showing() first rather than assume it
    always appears.
    """

    def __init__(self, app_session):
        self._continue_button = BaseComponent(
            app_session, *CONFIRM_ACCOUNTS_CONTINUE_BUTTON_LOCATOR, "ConfirmAccountsContinueButton"
        )

    def click_continue(self) -> None:
        self._continue_button.click()
