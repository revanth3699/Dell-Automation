"""SourceTransferFlow.wait_for_transfer_to_start(): confirms Source progresses through
the post-pairing sequence after Target starts the transfer -- "We're searching this PC
for your files and settings." then "Are you ready to start your migration?" (confirmed
directly by the user, 2026-10-06: both auto-advance on their own, nothing to click --
just text assertions confirming the sequence actually happens, not stuck).

Confirmed live (2026-10-06): Source's own pairing finishes the instant the code is
accepted, well before Target necessarily reaches this point -- Target still has its own
"preparing your files" step to get through first (can take "a few minutes" per its own
on-screen text, see flows/target/transfer_flow.py), and "We're searching this PC..."
here only appears once Target clicks through to start the transfer. A multi-minute gap
before it shows up is therefore expected, not broken on its own.

Bug fixed here, confirmed live (2026-10-06): each wait used to be a single
is_searching()/is_ready_to_migrate() call with a long timeout -- BaseComponent.exists()
polls internally every 0.5s but only logs once, after the ENTIRE timeout either
succeeds or fails, so there was zero visible output for up to screen_timeout seconds.
That's indistinguishable from actually being stuck, especially stacked on top of
Target's own silent multi-minute wait. Now polls explicitly with a short per-check
timeout so exists()'s own debug log fires every cycle, giving live visibility into
whether this is still alive and searching rather than frozen.
"""

import time

from components.source.transfer_progress_screen import TransferProgressScreen
from factory.logger_factory import LoggerFactory


class SourceTransferFlow:
    def __init__(self, app_session):
        self.transfer_progress_screen = TransferProgressScreen(app_session)
        self.log = LoggerFactory.get_logger("source")

    def _poll_until_showing(self, check, timeout: float, what: str) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if check(timeout=1.0):
                return
        raise RuntimeError(f"{what} never appeared within {timeout:.0f}s")

    def wait_for_transfer_to_start(self, screen_timeout: float = 600.0) -> None:
        self.log.info('Waiting for "We\'re searching this PC for your files and settings."...')
        self._poll_until_showing(
            self.transfer_progress_screen.is_searching,
            screen_timeout,
            '"We\'re searching this PC for your files and settings."',
        )
        self.log.success("Searching-files screen confirmed")

        self.log.info('Waiting for "Are you ready to start your migration?"...')
        self._poll_until_showing(
            self.transfer_progress_screen.is_ready_to_migrate,
            screen_timeout,
            '"Are you ready to start your migration?"',
        )
        self.log.success("Ready-to-migrate screen confirmed")
