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
