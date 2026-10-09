"""SourceTransferFlow.wait_for_transfer_to_start(): confirms Source progresses through
the post-pairing sequence after Target starts the transfer -- "We've successfully
linked your PCs." (brief, confirmed from a user-supplied screenshot, 2026-10-06, but not
confirmed to always appear) -> "Are you ready to start your migration?" (confirmed
directly by the user, 2026-10-06: neither needs a click -- just text assertions
confirming the sequence actually happens, not stuck). The first screen is checked with
a short, bounded timeout; if it's not seen in time, this falls straight through to the
next check instead of treating that as a failure -- it's a brief confirmation, not a
required gate.

"We're searching this PC for your files and settings." is deliberately NOT checked here
(omitted per explicit user direction, 2026-10-06) -- confirmed live that waiting on it
depends entirely on Target's own pace (it only appears once Target clicks through its
"preparing your files" step, which can take minutes), making it a weak, slow gate rather
than a useful assertion.

Confirmed live (2026-10-06): Source's own pairing finishes the instant the code is
accepted, well before Target necessarily reaches this point.

Bug fixed here, confirmed live (2026-10-06): each wait used to be a single
is_searching()/is_ready_to_migrate()-style call with a long timeout -- BaseComponent.
exists() polls internally every 0.5s but only logs once, after the ENTIRE timeout
either succeeds or fails, so there was zero visible output for up to screen_timeout
seconds. That's indistinguishable from actually being stuck. Now polls explicitly with
a short per-check timeout so exists()'s own debug log fires every cycle, giving live
visibility into whether this is still alive rather than frozen.
"""

import time

from components.source.transfer_progress_screen import TransferProgressScreen
from factory.logger_factory import LoggerFactory


class SourceTransferFlow:
    def __init__(self, app_session):
        self.transfer_progress_screen = TransferProgressScreen(app_session)
        self.log = LoggerFactory.get_logger("source")

    def _poll_until_showing(self, check, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if check(timeout=1.0):
                return True
        return False

    def wait_for_transfer_to_start(self, screen_timeout: float = 600.0, linked_success_timeout: float = 15.0) -> None:
        self.log.info('Checking for "We\'ve successfully linked your PCs."...')
        if self._poll_until_showing(self.transfer_progress_screen.is_linked_success, linked_success_timeout):
            self.log.success("Linked-success confirmation seen")
        else:
            self.log.info(
                '"We\'ve successfully linked your PCs." not seen within '
                f"{linked_success_timeout:.0f}s -- continuing to the next screen anyway "
                "(not every run shows it)"
            )

        self.log.info('Waiting for "Are you ready to start your migration?"...')
        if not self._poll_until_showing(self.transfer_progress_screen.is_ready_to_migrate, screen_timeout):
            raise RuntimeError(
                f'"Are you ready to start your migration?" never appeared within '
                f"{screen_timeout:.0f}s"
            )
        self.log.success("Ready-to-migrate screen confirmed")

    def wait_for_migration_to_complete(
        self, migrating_timeout: float = 60.0, summary_timeout: float = 1800.0, complete_timeout: float = 1800.0
    ) -> None:
        """Call after wait_for_transfer_to_start() returns. Confirmed from user-supplied
        screenshots: "We're migrating your data now." (confirms migration actually
        started, 2026-10-07) -> "Your migration summary is ready." (confirms it
        finished, 2026-10-07) -> "We've completed your migration." (the real final
        screen, confirmed 2026-10-09). The first two need no click, just confirmation
        the sequence is progressing; the third has the "Close" button that's actually
        clicked.

        Bug fixed here, confirmed directly by the user (2026-10-09): Close used to be
        clicked on "Your migration summary is ready." -- that was premature, not the
        app's own intended final action. "We've completed your migration." only appears
        once Target PC's own user clicks Finish and Target is redirected back to its
        home screen, so complete_timeout is a genuinely cross-machine, human-paced wait
        with no fixed bound -- defaults to 30 minutes, same reasoning as summary_timeout.
        """
        self.log.info('Waiting for "We\'re migrating your data now."...')
        if not self._poll_until_showing(self.transfer_progress_screen.is_migrating, migrating_timeout):
            raise RuntimeError(f'"We\'re migrating your data now." never appeared within {migrating_timeout:.0f}s')
        self.log.success("Migrating-data screen confirmed")

        self.log.info('Waiting for "Your migration summary is ready."...')
        if not self._poll_until_showing(self.transfer_progress_screen.is_summary_ready, summary_timeout):
            raise RuntimeError(
                f'"Your migration summary is ready." never appeared within {summary_timeout:.0f}s'
            )
        self.log.success("Migration summary ready")

        self.log.info(
            'Waiting for "We\'ve completed your migration." (appears only after Target '
            "PC's own user clicks Finish and returns to its home screen)..."
        )
        if not self._poll_until_showing(self.transfer_progress_screen.is_migration_complete, complete_timeout):
            raise RuntimeError(
                f'"We\'ve completed your migration." never appeared within {complete_timeout:.0f}s'
            )
        self.log.success("Migration complete confirmed -- clicking Close")
        self.transfer_progress_screen.close_migration_complete()
