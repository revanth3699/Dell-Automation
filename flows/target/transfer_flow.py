"""TargetTransferFlow: starts the file transfer once pairing has succeeded.

Confirmed from a user-supplied screenshot (2026-10-06): after pairing (and the
account-mismatch confirm dialog, if shown -- already handled inside
flows/target/pairing_flow.py's TargetPairingFlow), the app shows "We're preparing your
files and settings in your previous PC" (a pure wait, nothing to click, can genuinely
take a few minutes per its own on-screen text), then "Your files are ready to move".
start_transfer() waits for that second screen and clicks the default "Bring everything
over for me" option. Actually waiting for the transfer itself to finish is separate,
not yet built (see this module's wait_for_completion() stub reference in
PROJECT_PLAN.md) -- out of scope for what's confirmed/asked so far.
"""

from components.target.transfer_receive_screen import TransferReceiveScreen
from factory.logger_factory import LoggerFactory


class TransferFlowError(Exception):
    pass


class TargetTransferFlow:
    def __init__(self, app_session):
        self.transfer_receive_screen = TransferReceiveScreen(app_session)
        self.log = LoggerFactory.get_logger("target")

    def start_transfer(self, screen_timeout: float = 300.0) -> None:
        """Waits up to screen_timeout for "Your files are ready to move" -- the
        preceding "preparing your files" step can genuinely take a few minutes per its
        own on-screen text, so this defaults much longer than a normal screen
        transition -- then clicks "Bring everything over for me" to start the
        transfer.
        """
        self.log.info('Waiting for "Your files are ready to move" (Target is preparing/scanning files)...')
        if not self.transfer_receive_screen.wait_until_showing(timeout=screen_timeout):
            raise TransferFlowError(
                f'"Your files are ready to move" screen never appeared within {screen_timeout:.0f}s'
            )
        self.log.success('Files ready to move -- starting transfer ("Bring everything over for me")')
        self.transfer_receive_screen.start_transfer()
