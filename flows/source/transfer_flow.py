"""SourceTransferFlow.wait_for_transfer_to_start(): confirms Source progresses through
the post-pairing sequence after Target starts the transfer -- "We're searching this PC
for your files and settings." then "Are you ready to start your migration?" (confirmed
directly by the user, 2026-10-06: both auto-advance on their own, nothing to click --
just text assertions confirming the sequence actually happens, not stuck).
"""

from components.source.transfer_progress_screen import TransferProgressScreen
from factory.logger_factory import LoggerFactory


class SourceTransferFlow:
    def __init__(self, app_session):
        self.transfer_progress_screen = TransferProgressScreen(app_session)
        self.log = LoggerFactory.get_logger("source")

    def wait_for_transfer_to_start(self, screen_timeout: float = 300.0) -> None:
        self.log.info('Waiting for "We\'re searching this PC for your files and settings."...')
        if not self.transfer_progress_screen.is_searching(timeout=screen_timeout):
            raise RuntimeError('"We\'re searching this PC for your files and settings." never appeared')
        self.log.success("Searching-files screen confirmed")

        self.log.info('Waiting for "Are you ready to start your migration?"...')
        if not self.transfer_progress_screen.is_ready_to_migrate(timeout=screen_timeout):
            raise RuntimeError('"Are you ready to start your migration?" never appeared')
        self.log.success("Ready-to-migrate screen confirmed")
