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
current code to the Coordination Service (see utils/coordination_client.py) for this
flow to fetch -- see enter_pairing_code_from_coordination_service() below.
"""

import time
from typing import Optional

import requests

from components.base_component import ComponentActionError
from components.target.common_dialogs import NetworkDisconnectedDialog
from components.target.pairing_code_entry_screen import ConfirmAccountsDialog, PairingCodeEntryScreen
from utils.coordination_client import PAIRING_CODE_KEY, CoordinationClient
from factory.logger_factory import LoggerFactory


class PairingError(Exception):
    pass


# Exception types a single fetch+enter attempt can actually raise underneath
# _submit_code_and_confirm(), beyond this module's own PairingError: enter_code() can
# raise ComponentActionError directly, or TimeoutError via poll_until() when the
# code-entry boxes never appear; the raw box.send_keys() call (bypassing
# BaseComponent's own exception-wrapping) can raise RuntimeError after exhausting its
# own retries, or a requests exception straight from WinAppDriverElement._post(). All
# of these are exactly the kind of single-rotation, transient failure
# enter_pairing_code_from_coordination_service()'s retry loop exists to survive -- not
# just PairingError.
_RETRYABLE_PAIRING_ENTRY_EXCEPTIONS = (
    PairingError,
    ComponentActionError,
    TimeoutError,
    RuntimeError,
    requests.exceptions.RequestException,
)


class TargetPairingFlow:
    def __init__(self, app_session):
        self.app_session = app_session
        self.log = LoggerFactory.get_logger("target")
        self.pairing_code_entry_screen = PairingCodeEntryScreen(app_session)
        self.confirm_accounts_dialog = ConfirmAccountsDialog(app_session)
        self.network_disconnected_dialog = NetworkDisconnectedDialog(app_session)

    def _poll_with_network_recovery(self, condition_fn, timeout: float, poll_interval: float = 1.0) -> bool:
        """Polls condition_fn() every poll_interval seconds up to timeout, transparently
        recovering from the "This PC isn't connected to a network." dialog if it appears
        in the meantime. Confirmed directly by the user via a live screenshot
        (2026-10-09): this dialog can appear at ANY point during pairing (not tied to one
        specific step) and is not a terminal error -- NetworkDisconnectedDialog.accept()
        (components/target/common_dialogs.py) already waits 30s before clicking its own
        "Check again" button, so this just calls that and keeps waiting on the original
        condition. Both `_wait_for_screen()` and `_submit_code_and_confirm()` below go
        through this, since the dialog isn't specific to either one.

        Uses the same NetworkDisconnectedDialog as flows/target/authentication/
        sign_in_flow.py and flows/source/pairing_flow.py (not a separate copy) -- see
        that class's own docstring.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition_fn():
                return True
            if self.network_disconnected_dialog.accept(timeout=0.1):
                self.log.info(
                    "\"This PC isn't connected to a network\" appeared -- waited and "
                    "clicked Check again"
                )
                continue
            time.sleep(poll_interval)
        return False

    def _wait_for_screen(self, screen_timeout: float) -> None:
        self.log.info("Waiting for the pairing-code entry screen (\"Let's connect your two PCs\")")
        if not self._poll_with_network_recovery(
            lambda: self.pairing_code_entry_screen.is_showing(timeout=0.1), max(screen_timeout, 5.0)
        ):
            raise PairingError(
                "Pairing-code entry screen (\"Let's connect your two PCs\") never appeared "
                "after Source PC was found"
            )
        self.log.success("Pairing-code entry screen showing")

    def _submit_code_and_confirm(self, code: str, advance_timeout: float) -> None:
        self.pairing_code_entry_screen.enter_code(code)

        self.log.info("Waiting for the pairing-code entry screen to clear (code accepted)")
        if not self._poll_with_network_recovery(
            lambda: not self.pairing_code_entry_screen.is_showing(timeout=0.1), advance_timeout
        ):
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
        max_attempts: int = 3,
    ) -> None:
        """Same end result as enter_pairing_code(), but fetches the code from the
        Coordination Service (published by the independent Source-side process -- see
        flows/source/pairing_flow.py's SourcePairingFlow) instead of requiring the
        caller to already have it.

        Fetches the code AFTER this screen is already showing, not before -- the code
        on the Source side rotates every ~59s (confirmed directly by the user,
        2026-10-06; see SourcePairingFlow's own docstring), so fetching as late as
        possible, right before typing, minimizes the chance the code rotates out from
        under us mid-entry. fetch_timeout bounds the
        wait for Source to have published ANY value yet (defaults to the app's own
        confirmed 10-minute pairing timeout); it is not a per-rotation budget.

        Confirmed live (2026-10-06): fetching late isn't always enough on its own --
        typing all 6 digits (each box's own deliberate click/settle/verify cycle, see
        WinAppDriverElement.send_keys()) took ~11s in one observed run, long enough for
        the fetched code to rotate out from under us before the app finishes validating
        it, leaving the entry screen showing after advance_timeout with no further
        progress. Retries the whole fetch+enter cycle up to max_attempts times on that
        specific failure -- Source's publish loop republishes every
        CODE_REPUBLISH_INTERVAL_SECONDS (5s), so a retry's fresh fetch is very likely to
        return whatever code is CURRENTLY valid rather than the one that just expired.
        """
        coordination_client = coordination_client or CoordinationClient()
        self._wait_for_screen(screen_timeout)

        last_error: Optional[Exception] = None
        for attempt in range(1, max_attempts + 1):
            self.log.info(
                f"Fetching current pairing code from Coordination Service "
                f"(run_id={run_id!r}, attempt {attempt}/{max_attempts})"
            )
            code = coordination_client.wait_for(run_id, PAIRING_CODE_KEY, timeout=fetch_timeout)
            self.log.success(f"Fetched pairing code: {code}")

            try:
                self._submit_code_and_confirm(code, advance_timeout)
                return
            except _RETRYABLE_PAIRING_ENTRY_EXCEPTIONS as exc:
                last_error = exc
                self.log.warning(
                    f"Attempt {attempt}/{max_attempts} failed ({type(exc).__name__}: {exc}) "
                    "-- re-fetching the current code and retrying, in case it rotated on "
                    "the Source side during entry, or a WinAppDriver/network hiccup during "
                    "digit entry"
                )
        raise last_error
