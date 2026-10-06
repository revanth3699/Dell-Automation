"""TargetTransferFlow: starts the file transfer once pairing has succeeded.

Confirmed from a user-supplied screenshot (2026-10-06): after pairing, the app shows
"We're preparing your files and settings in your previous PC" (can genuinely take a
few minutes per its own on-screen text), then "Your files are ready to move".
start_transfer() waits for that second screen and clicks the default "Bring everything
over for me" option. Actually waiting for the transfer itself to finish is separate,
not yet built (see this module's wait_for_completion() stub reference in
PROJECT_PLAN.md) -- out of scope for what's confirmed/asked so far.

Bug fixed here, confirmed live (2026-10-06): the account-mismatch confirm dialog
("Let's make sure we're connecting the right user accounts") does NOT reliably appear
within the brief 5s window flows/target/pairing_flow.py's TargetPairingFlow checks for
right after the pairing code is accepted -- confirmed via a live screenshot showing it
appearing layered OVER the "preparing your files" screen instead, well into this
method's wait. That 5s check isn't removed (harmless if it already caught it), but
start_transfer() now also races the confirm dialog against "Your files are ready to
move" for its entire wait, so a late-appearing dialog gets clicked instead of silently
blocking everything with nothing to watch for it.

Also races "We need to close all other applications" (confirmed from a user-supplied
screenshot, 2026-10-06) the same way -- shown when other apps (Control Panel, a
browser, etc.) are open and blocking migration. Unlike the confirm-accounts dialog this
isn't gated to "only once": it's checked and accepted every cycle, since there's no
confirmed guarantee it can't reappear if another conflicting app gets detected later.
"""

import time

from components.target.common_dialogs import CloseAppsDialog
from components.target.pairing_code_entry_screen import ConfirmAccountsDialog
from components.target.transfer_receive_screen import TransferReceiveScreen
from factory.logger_factory import LoggerFactory


class TransferFlowError(Exception):
    pass


class TargetTransferFlow:
    def __init__(self, app_session):
        self.transfer_receive_screen = TransferReceiveScreen(app_session)
        self.confirm_accounts_dialog = ConfirmAccountsDialog(app_session)
        self.close_apps_dialog = CloseAppsDialog(app_session)
        self.log = LoggerFactory.get_logger("target")

    def start_transfer(self, screen_timeout: float = 300.0) -> None:
        """Waits up to screen_timeout for "Your files are ready to move" -- the
        preceding "preparing your files" step can genuinely take a few minutes per its
        own on-screen text, so this defaults much longer than a normal screen
        transition -- then clicks "Bring everything over for me" to start the
        transfer. Races the account-mismatch confirm dialog and the close-other-apps
        dialog the whole time too (see module docstring) and clicks through either.
        """
        self.log.info('Waiting for "Your files are ready to move" (Target is preparing/scanning files)...')
        deadline = time.monotonic() + screen_timeout
        confirmed_accounts = False
        while time.monotonic() < deadline:
            if self.transfer_receive_screen.wait_until_showing(timeout=0.5):
                self.log.success('Files ready to move -- starting transfer ("Bring everything over for me")')
                self.transfer_receive_screen.start_transfer()
                return
            if not confirmed_accounts and self.confirm_accounts_dialog.accept(timeout=0.1):
                self.log.success(
                    "Account-mismatch confirm dialog appeared during the "
                    "preparing-files wait -- clicked Continue"
                )
                confirmed_accounts = True
            if self.close_apps_dialog.accept(timeout=0.1):
                self.log.success(
                    "\"We need to close all other applications\" appeared -- clicked "
                    "Close Application"
                )
        raise TransferFlowError(
            f'"Your files are ready to move" screen never appeared within {screen_timeout:.0f}s'
        )
