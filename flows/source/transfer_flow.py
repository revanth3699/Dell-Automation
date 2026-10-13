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

Per explicit user direction (2026-10-14): this file holds no existence-check locators.
Every is_X_showing()/is_X_confirmed() assertion is imported directly from
assertions/source/transfer_progress_screen.py and called with the raw app_session;
components/source/transfer_progress_screen.py now holds only the click_close()
action.

wait_for_migration_to_complete() races TWO possible final screens, not one -- see its
own docstring for why (confirmed via two user-supplied screenshots, 2026-10-14: a full
success shows "We've completed your migration.", a partial migration shows "Your
migration summary is ready." instead; either is a legitimate end state).
"""

import time

from components.source.transfer_progress_screen import TransferProgressScreen
from assertions.source import transfer_progress_screen as transfer_progress_assertions
from factory.logger_factory import LoggerFactory


class SourceTransferFlow:
    def __init__(self, app_session):
        self.app_session = app_session
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
        if self._poll_until_showing(
            lambda timeout: transfer_progress_assertions.is_linked_success(self.app_session, timeout=timeout),
            linked_success_timeout,
        ):
            self.log.success("Linked-success confirmation seen")
        else:
            self.log.info(
                '"We\'ve successfully linked your PCs." not seen within '
                f"{linked_success_timeout:.0f}s -- continuing to the next screen anyway "
                "(not every run shows it)"
            )

        self.log.info('Waiting for "Are you ready to start your migration?"...')
        if not self._poll_until_showing(
            lambda timeout: transfer_progress_assertions.is_ready_to_migrate(self.app_session, timeout=timeout),
            screen_timeout,
        ):
            raise RuntimeError(
                f'"Are you ready to start your migration?" never appeared within '
                f"{screen_timeout:.0f}s"
            )
        self.log.success("Ready-to-migrate screen confirmed")

    def wait_for_migration_to_complete(
        self, migrating_timeout: float = 60.0, summary_timeout: float = 1800.0
    ) -> bool:
        """Call after wait_for_transfer_to_start() returns. Confirmed from user-supplied
        screenshots: "We're migrating your data now." (confirms migration actually
        started, 2026-10-07) -> one of two final screens (2026-10-14):

          - "We've completed your migration." -- full success, every file and setting
            migrated.
          - "Your migration summary is ready." -- partial migration, some data was
            skipped (body text explicitly says so -- see
            assertions.source.transfer_progress_screen's own docstring).

        The outcome isn't known in advance, so both are raced every cycle (each
        confirmed via its own heading + body text together, not the heading alone) --
        same "race it, don't assume" pattern used throughout this project for
        unpredictable dialogs. Both screens share one "Close" button (same accessible
        name), clicked here either way once whichever one is confirmed.

        Returns True if migration completed fully, False if it completed with some
        data skipped (partial). Raises if neither final screen is confirmed within
        summary_timeout.

        Bug fixed here, confirmed directly by the user via two live runs (2026-10-13,
        2026-10-14): this used to poll ONLY for "Your migration summary is ready." --
        in a run where migration genuinely succeeded in full, that heading never
        appears at all ("We've completed your migration." shows instead), so this
        polled indefinitely against a screen that was never coming.
        """
        self.log.info('Waiting for "We\'re migrating your data now."...')
        if not self._poll_until_showing(
            lambda timeout: transfer_progress_assertions.is_migrating(self.app_session, timeout=timeout),
            migrating_timeout,
        ):
            raise RuntimeError(f'"We\'re migrating your data now." never appeared within {migrating_timeout:.0f}s')
        self.log.success("Migrating-data screen confirmed")

        self.log.info(
            'Waiting for the final screen -- racing "We\'ve completed your migration." '
            '(full success) against "Your migration summary is ready." (partial), each '
            "confirmed via heading + body text..."
        )
        deadline = time.monotonic() + summary_timeout
        migration_complete = None
        while time.monotonic() < deadline:
            if transfer_progress_assertions.is_migration_complete_confirmed(self.app_session, timeout=1.0):
                migration_complete = True
                break
            if transfer_progress_assertions.is_summary_confirmed(self.app_session, timeout=1.0):
                migration_complete = False
                break
        if migration_complete is None:
            raise RuntimeError(
                'Neither "We\'ve completed your migration." nor "Your migration summary '
                f'is ready." was confirmed within {summary_timeout:.0f}s'
            )

        if migration_complete:
            self.log.success(
                '"We\'ve completed your migration." confirmed -- migration fully '
                "successful, clicking Close"
            )
        else:
            self.log.warning(
                '"Your migration summary is ready." confirmed -- migration partial '
                "(some data was skipped), clicking Close"
            )
        self.transfer_progress_screen.click_close()
        return migration_complete
