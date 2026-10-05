"""
TargetPairingFlow: orchestrates the pairing-code exchange once SignInFlow.run() has
reached the pairing-discovery screen and SignInFlow.wait_for_source_pc() has confirmed
Source PC was found. Confirmed sequence from a user-supplied flow diagram (dell screens
flow.pdf, 2026-10-05): "We're looking for your other PC" clears -> "Let's connect your
two PCs" (enter the verification code shown on Source PC) -> if accepted AND the two PCs'
account names differ, a "Let's make sure we're connecting the right user accounts"
confirm dialog -> file-selection screen ("Your files are ready to move" -- out of scope
here, a later phase of the migration, not part of pairing).

Target-PC-only, same as SignInFlow -- Source PC's side of this exchange (showing its own
code) is separate, not-yet-built work (blocked on Source PC build access, see
PROJECT_PLAN.md Sec 10, open item 1).
"""

from components.target.pairing_code_entry_screen import ConfirmAccountsDialog, PairingCodeEntryScreen
from factory.logger_factory import LoggerFactory


class PairingError(Exception):
    pass


class TargetPairingFlow:
    def __init__(self, app_session):
        self.app_session = app_session
        self.log = LoggerFactory.get_logger("target")
        self.pairing_code_entry_screen = PairingCodeEntryScreen(app_session)
        self.confirm_accounts_dialog = ConfirmAccountsDialog(app_session)

    def enter_pairing_code(self, code: str, screen_timeout: float = 30.0, advance_timeout: float = 30.0) -> None:
        """Call after SignInFlow.wait_for_source_pc() returns True. Waits for the
        "Let's connect your two PCs" screen, enters the code, waits for it to clear
        (confirming the code was accepted), and handles the account-mismatch confirm
        dialog if it appears.
        """
        self.log.info("Waiting for the pairing-code entry screen (\"Let's connect your two PCs\")")
        if not self.pairing_code_entry_screen.wait_until_showing(timeout=screen_timeout):
            raise PairingError(
                "Pairing-code entry screen (\"Let's connect your two PCs\") never appeared "
                "after Source PC was found"
            )
        self.log.success("Pairing-code entry screen showing -- entering code")
        self.pairing_code_entry_screen.enter_code(code)

        self.log.info("Waiting for the pairing-code entry screen to clear (code accepted)")
        if not self.pairing_code_entry_screen.wait_until_gone(timeout=advance_timeout):
            raise PairingError(
                f"Pairing-code entry screen still showing after {advance_timeout:.0f}s -- "
                "the code may have been rejected (no confirmed error-message text for "
                "this screen yet -- check a screenshot)"
            )
        self.log.success("Pairing code accepted")

        # Not every pairing shows this -- only when the two PCs' account names differ
        # (confirmed from the reference diagram).
        if self.confirm_accounts_dialog.accept(timeout=5.0):
            self.log.success(
                "Account-mismatch confirm dialog appeared (\"Let's make sure we're "
                "connecting the right user accounts\") -- clicked Continue"
            )
        else:
            self.log.info("Account-mismatch confirm dialog did not appear -- account names matched")
