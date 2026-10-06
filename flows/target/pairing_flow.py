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
code) lives under flows/source/pairing_flow.py (SourcePairingFlow), which publishes the
current code to the Coordination Service (see factory/coordination_client.py) for this
flow to fetch -- see enter_pairing_code_from_coordination_service() below.
"""

from typing import Optional

from components.target.pairing_code_entry_screen import ConfirmAccountsDialog, PairingCodeEntryScreen
from factory.coordination_client import PAIRING_CODE_KEY, CoordinationClient
from factory.logger_factory import LoggerFactory


class PairingError(Exception):
    pass


class TargetPairingFlow:
    def __init__(self, app_session):
        self.app_session = app_session
        self.log = LoggerFactory.get_logger("target")
        self.pairing_code_entry_screen = PairingCodeEntryScreen(app_session)
        self.confirm_accounts_dialog = ConfirmAccountsDialog(app_session)

    def _wait_for_screen(self, screen_timeout: float) -> None:
        self.log.info("Waiting for the pairing-code entry screen (\"Let's connect your two PCs\")")
        if not self.pairing_code_entry_screen.wait_until_showing(timeout=screen_timeout):
            raise PairingError(
                "Pairing-code entry screen (\"Let's connect your two PCs\") never appeared "
                "after Source PC was found"
            )
        self.log.success("Pairing-code entry screen showing")

    def _submit_code_and_confirm(self, code: str, advance_timeout: float) -> None:
        self.pairing_code_entry_screen.enter_code(code)

        self.log.info("Waiting for the pairing-code entry screen to clear (code accepted)")
        if not self.pairing_code_entry_screen.wait_until_gone(timeout=advance_timeout):
            raise PairingError(
                f"Pairing-code entry screen still showing after {advance_timeout:.0f}s -- "
                "the code may have been rejected (no confirmed error-message text for "
                "this screen yet -- check a screenshot), or it rotated on the Source side "
                "before entry completed"
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

    def enter_pairing_code(self, code: str, screen_timeout: float = 30.0, advance_timeout: float = 30.0) -> None:
        """Call after SignInFlow.wait_for_source_pc() returns True, with a code you
        already have in hand (e.g. from a CLI arg -- see tools/run_sign_in_flow.py).
        Waits for the "Let's connect your two PCs" screen, enters the code, waits for it
        to clear (confirming the code was accepted), and handles the account-mismatch
        confirm dialog if it appears.
        """
        self._wait_for_screen(screen_timeout)
        self.log.info("Entering code")
        self._submit_code_and_confirm(code, advance_timeout)

    def enter_pairing_code_from_coordination_service(
        self,
        run_id: str,
        coordination_client: Optional[CoordinationClient] = None,
        fetch_timeout: float = 600.0,
        screen_timeout: float = 30.0,
        advance_timeout: float = 30.0,
    ) -> None:
        """Same end result as enter_pairing_code(), but fetches the code from the
        Coordination Service (published by the independent Source-side process -- see
        flows/source/pairing_flow.py's SourcePairingFlow) instead of requiring the
        caller to already have it.

        Fetches the code AFTER this screen is already showing, not before -- the code
        on the Source side rotates roughly every ~60s (see SourcePairingFlow's own
        docstring), so fetching as late as possible, right before typing, minimizes the
        chance the code rotates out from under us mid-entry. fetch_timeout bounds the
        wait for Source to have published ANY value yet (defaults to the app's own
        confirmed 10-minute pairing timeout); it is not a per-rotation budget.
        """
        coordination_client = coordination_client or CoordinationClient()
        self._wait_for_screen(screen_timeout)

        self.log.info(f"Fetching current pairing code from Coordination Service (run_id={run_id!r})")
        code = coordination_client.wait_for(run_id, PAIRING_CODE_KEY, timeout=fetch_timeout)
        self.log.success(f"Fetched pairing code: {code}")

        self._submit_code_and_confirm(code, advance_timeout)
