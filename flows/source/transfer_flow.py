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

wait_for_migration_to_complete() races THREE possible final screens, not one or two --
see its own docstring for why (confirmed via user-supplied screenshots across multiple
live runs: a full success shows "We've completed your migration.", and a partial
migration can show EITHER "Your migration is now complete." or "Your migration summary
is ready." -- this project was bitten by assuming only one of those two was ever real,
twice, before confirming both are legitimate partial-migration end states).

Bug fixed here, confirmed by the user via a live screenshot (2026-10-13):
BatteryCriticallyLowDialog ("Your battery is critically low." -- Cancel) was wired into
pairing_flow.py only. It can appear at any point, including during this whole
post-pairing transfer sequence, so per this project's own "race it continuously"
pattern (see CLAUDE.md) it's now raced every cycle here too -- in _poll_until_showing()
(covers linked-success/ready-to-migrate/migrating-data) and in the final-screen loop in
wait_for_migration_to_complete().

Bug fixed here, confirmed via user-supplied screenshots (2026-10-13): clicking Cancel
on BatteryCriticallyLowDialog does NOT just dismiss it -- it triggers
ConfirmCancelDialog ("Are you sure you want to cancel?"), asking to confirm cancelling
the WHOLE migration. Without handling this, the run would sit on that confirmation
until its own timeout, or (worse) could accidentally cancel the migration if something
else clicked through it. _check_battery_critically_low() now checks for and dismisses
it immediately (via "No, don't cancel") right after every click_cancel() -- see
assertions/source/confirm_cancel_dialog.py's own docstring.
"""

import time

from components.source.battery_critically_low_dialog import BatteryCriticallyLowDialog
from components.source.confirm_cancel_dialog import ConfirmCancelDialog
from components.source.other_pc_network_disconnected_dialog import OtherPcNetworkDisconnectedDialog
from components.source.transfer_progress_screen import TransferProgressScreen
from assertions.source import battery_critically_low_dialog as battery_critically_low_assertions
from assertions.source import confirm_cancel_dialog as confirm_cancel_assertions
from assertions.source import other_pc_network_disconnected_dialog as other_pc_network_disconnected_assertions
from assertions.source import transfer_progress_screen as transfer_progress_assertions
from factory.logger_factory import LoggerFactory


class SourceTransferFlow:
    def __init__(self, app_session):
        self.app_session = app_session
        self.transfer_progress_screen = TransferProgressScreen(app_session)
        self.battery_critically_low_dialog = BatteryCriticallyLowDialog(app_session)
        self.confirm_cancel_dialog = ConfirmCancelDialog(app_session)
        self.other_pc_network_disconnected_dialog = OtherPcNetworkDisconnectedDialog(app_session)
        self.log = LoggerFactory.get_logger("source")

    def _check_battery_critically_low(self) -> bool:
        if not battery_critically_low_assertions.is_showing(self.app_session, timeout=0.1):
            return False
        self.log.warning('Your battery is critically low. appeared -- clicking Cancel')
        self.battery_critically_low_dialog.click_cancel()
        if confirm_cancel_assertions.is_showing(self.app_session, timeout=2.0):
            self.log.warning(
                'Are you sure you want to cancel? appeared after dismissing the '
                "battery dialog -- clicking No, don't cancel"
            )
            self.confirm_cancel_dialog.click_no_dont_cancel()
        return True

    def _check_other_pc_disconnected(self) -> bool:
        """Shared by every wait loop in this class, same reasoning as
        _check_battery_critically_low(). Confirmed directly by the user via a live
        screenshot (2026-10-14): "The other PC isn't connected to a network." means
        the Target PC lost its network connection.

        Bug fixed here, confirmed directly by the user (2026-10-14): this used to
        click "Cancel transfer" and then raise, aborting the whole run (mirroring
        Target's own OtherPcNetworkDisconnectedDialog, which IS confirmed terminal
        there) -- but on Source this isn't fatal. Just clicks "Cancel transfer" and
        lets the caller's loop continue, same "race it, click through, keep going"
        pattern as every other dialog in this class."""
        if not other_pc_network_disconnected_assertions.is_showing(self.app_session, timeout=0.1):
            return False
        self.other_pc_network_disconnected_dialog.click_cancel_transfer()
        self.log.warning("The other PC isn't connected to a network. appeared -- clicked Cancel transfer")
        return True

    def _poll_until_showing(self, check, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._check_other_pc_disconnected():
                continue
            if self._check_battery_critically_low():
                continue
            if check(timeout=1.0):
                return True
        return False

    def wait_for_transfer_to_start(self, screen_timeout: float = 600.0, linked_success_timeout: float = 15.0) -> None:
        self.log.info("Checking for We've successfully linked your PCs. ...")
        if self._poll_until_showing(
            lambda timeout: transfer_progress_assertions.is_linked_success(self.app_session, timeout=timeout),
            linked_success_timeout,
        ):
            self.log.success("Linked-success confirmation seen")
        else:
            self.log.info(
                "We've successfully linked your PCs. not seen within "
                f"{linked_success_timeout:.0f}s -- continuing to the next screen anyway "
                "(not every run shows it)"
            )

        self.log.info("Waiting for Are you ready to start your migration? ...")
        if not self._poll_until_showing(
            lambda timeout: transfer_progress_assertions.is_ready_to_migrate(self.app_session, timeout=timeout),
            screen_timeout,
        ):
            raise RuntimeError(
                f"Are you ready to start your migration? never appeared within "
                f"{screen_timeout:.0f}s"
            )
        self.log.success("Ready-to-migrate screen confirmed")

    def wait_for_migration_to_complete(
        self, migrating_timeout: float = 60.0, summary_timeout: float = 1800.0
    ) -> bool:
        """Call after wait_for_transfer_to_start() returns. Confirmed from user-supplied
        screenshots: "We're migrating your data now." (confirms migration actually
        started, 2026-10-07) -> one of THREE final screens:

          - "We've completed your migration." -- full success, every file and setting
            migrated. Has a "Close" button.
          - "Your migration is now complete." -- one of two partial-migration outcomes,
            some data was skipped (body text explicitly says so -- see
            assertions.source.transfer_progress_screen's own docstring). Has a "Try
            Again" button, NOT a "Close" button -- dismissed via its own close icon
            instead (see components.source.transfer_progress_screen.click_close_icon()).
          - "Your migration summary is ready." -- the OTHER partial-migration outcome.
            Has a "Close" button, same accessible name as the full-success screen's,
            but dismissed via click_close_after_delay() instead of click_close() --
            per explicit user direction (2026-10-13), this one waits
            TransferProgressScreen.PARTIAL_SUMMARY_CLOSE_DELAY_SECONDS before clicking,
            giving the user a chance to read the summary / use Show skipped files
            first, rather than being dismissed immediately like full success.

        Also races, every cycle, the recoverable "We ran into a problem during your
        migration." error screen (confirmed via a user-supplied screenshot, 2026-10-13)
        -- NOT a final outcome, so it doesn't break the loop: its own "Try Again"
        button is clicked and polling continues, since the migration restarts and will
        eventually land on one of the three real final screens (or this error screen
        again).

        The outcome isn't known in advance, so all three final screens are raced every
        cycle (each confirmed via its own heading + body text together, not the heading
        alone) -- same "race it, don't assume" pattern used throughout this project for
        unpredictable dialogs.

        Returns True if migration completed fully, False if it completed with some
        data skipped (partial, either variant). Raises if no final screen is confirmed
        within summary_timeout.

        Bug fixed here, confirmed directly by the user across THREE separate live runs
        (2026-10-13): this screen family kept flip-flopping between "Your migration
        summary is ready." and "Your migration is now complete." as THE one partial
        final screen, with each fix dropping whichever heading the previous live run
        hadn't shown -- so the dropped one caused the same indefinite-polling bug the
        very next time it appeared instead. Both are now raced as alternative partial
        outcomes rather than betting on one (see
        assertions.source.transfer_progress_screen's own module docstring for the full
        history). A separate, now-fixed bug from the same investigation: the final
        screens do NOT all share one "Close" button -- "Your migration is now
        complete." has no "Close" button at all and has to be dismissed via its own
        close icon instead.
        """
        self.log.info("Waiting for We're migrating your data now. ...")
        if not self._poll_until_showing(
            lambda timeout: transfer_progress_assertions.is_migrating(self.app_session, timeout=timeout),
            migrating_timeout,
        ):
            raise RuntimeError(f"We're migrating your data now. never appeared within {migrating_timeout:.0f}s")
        self.log.success("Migrating-data screen confirmed")

        self.log.info(
            "Waiting for the final screen -- racing We've completed your migration. "
            "(full success) against both Your migration is now complete. and Your "
            "migration summary is ready. (the two partial outcomes), and continuously "
            "watching for the recoverable We ran into a problem during your "
            "migration. error screen, each confirmed via heading + body text..."
        )
        deadline = time.monotonic() + summary_timeout
        migration_complete = None
        dismiss_action = None
        while time.monotonic() < deadline:
            if self._check_other_pc_disconnected():
                continue
            if self._check_battery_critically_low():
                continue
            if transfer_progress_assertions.is_migration_error_confirmed(self.app_session, timeout=0.1):
                self.log.warning(
                    "We ran into a problem during your migration. appeared -- "
                    "clicking Try Again"
                )
                self.transfer_progress_screen.click_try_again()
                continue
            if transfer_progress_assertions.is_migration_complete_confirmed(self.app_session, timeout=1.0):
                migration_complete = True
                dismiss_action = self.transfer_progress_screen.click_close
                break
            if transfer_progress_assertions.is_migration_partial_try_again_confirmed(self.app_session, timeout=1.0):
                migration_complete = False
                dismiss_action = self.transfer_progress_screen.click_close_icon
                break
            if transfer_progress_assertions.is_migration_partial_summary_confirmed(self.app_session, timeout=1.0):
                migration_complete = False
                dismiss_action = self.transfer_progress_screen.click_close_after_delay
                break
        if migration_complete is None:
            raise RuntimeError(
                "None of We've completed your migration., Your migration is now "
                "complete. or Your migration summary is ready. was confirmed within "
                f"{summary_timeout:.0f}s"
            )

        if migration_complete:
            self.log.success(
                "We've completed your migration. confirmed -- migration fully "
                "successful, clicking Close"
            )
        else:
            self.log.warning(
                "Partial-migration final screen confirmed (some data was skipped) -- "
                "dismissing it"
            )
        dismiss_action()
        return migration_complete
