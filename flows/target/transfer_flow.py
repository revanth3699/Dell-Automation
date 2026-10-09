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

Also, per explicit user direction (2026-10-06): the moment "Your files are ready to
move" is detected, the close-apps dialog is checked AGAIN, directly, right before
clicking "Migrate now" -- not just relying on the background race above. Same reasoning
as the confirm-accounts dialog surprising us by appearing layered OVER a screen we
thought was clear: a dialog detected one poll cycle earlier isn't a guarantee nothing
new appeared in the moment right before the click itself.

Confirmed from a user-supplied screenshot (2026-10-06): after that click, "We're moving
your files and settings" (the actual transfer-progress screen -- percentages, ETA,
transfer speed) appears. start_transfer() now polls for it to confirm the transfer
genuinely started, rather than returning right after the click with no confirmation
anything actually happened. Tracking progress/completion from there is separate, not
yet built.

Bug fixed here, confirmed live (2026-10-06): the close-apps dialog can ALSO appear
AFTER clicking Migrate now, layered over "Your files are ready to move" while waiting
for "We're moving your files and settings" to show up -- confirmed via a live
screenshot showing exactly this (the dialog over the still-visible "ready to move"
screen, Migrate now already clicked). The wait for the progress screen was a single
is_showing() call with no handling for this at all, so it would just burn the whole
timeout and fail. Now races the close-apps dialog here too, same as everywhere else.

Bug fixed here, confirmed live (2026-10-07): click_at_center() on "Migrate now"
reported success (no exception) but confirmed via screenshot that the button visually
never actually activated -- the same silent-click-doesn't-register class of problem,
just surviving even the click_at_center() workaround this time. Rather than trust a
single click, the wait for "We're moving your files and settings" now periodically
re-clicks "Migrate now" (every RECLICK_INTERVAL_SECONDS) for as long as neither it nor
the close-apps dialog has appeared -- since the button is presumably still right there
on the unchanged "ready to move" screen if the first click didn't take.

Bug fixed here, confirmed live (2026-10-08): a fatal engine-side error ("Something went
wrong ... (error 2969). Please close and try again.") can appear layered over the
transfer-progress screen mid-transfer -- confirmed both from a raw TargetPc log excerpt
("Engine reported error 2969 on MigrationStatus (Status=false) after pairing ->
FailurePage") and a live screenshot showing the dialog over the still-visible "0 B/s"/
"...minutes left" progress screen. Nothing previously detected this: wait_for_completion()'s
wait for the progress screen to clear was a single un-raced wait_until_gone() call, so
it would have silently burned up to the full transfer_timeout (30 minutes default)
before raising a generic "did not finish" error with the wrong cause attached. All
three wait loops in this file (start_transfer()'s two, wait_for_completion()'s one) now
race MigrationErrorDialog every cycle and raise immediately with the real error text if
it appears, same pattern as every other dialog race here.
"""

import time

from components.target.common_dialogs import CloseAppsDialog, MigrationErrorDialog
from components.target.migration_complete_screen import MigrationCompleteScreen
from components.target.migration_summary_screen import MigrationSummaryScreen
from components.target.pairing_code_entry_screen import ConfirmAccountsDialog
from components.target.transfer_progress_screen import TransferProgressScreen
from components.target.transfer_receive_screen import TransferReceiveScreen
from factory.logger_factory import LoggerFactory

RECLICK_INTERVAL_SECONDS = 3.0


class TransferFlowError(Exception):
    pass


class TargetTransferFlow:
    def __init__(self, app_session):
        self.transfer_receive_screen = TransferReceiveScreen(app_session)
        self.transfer_progress_screen = TransferProgressScreen(app_session)
        self.migration_summary_screen = MigrationSummaryScreen(app_session)
        self.migration_complete_screen = MigrationCompleteScreen(app_session)
        self.confirm_accounts_dialog = ConfirmAccountsDialog(app_session)
        self.close_apps_dialog = CloseAppsDialog(app_session)
        self.migration_error_dialog = MigrationErrorDialog(app_session)
        self.log = LoggerFactory.get_logger("target")

    def _raise_if_migration_error(self) -> None:
        """Shared by every wait loop in this class (confirmed via code review,
        2026-10-09: this exact 3-line check used to be copy-pasted at three separate
        call sites). Raises TransferFlowError immediately if "Something went wrong"
        is showing; a no-op otherwise."""
        if self.migration_error_dialog.is_showing(timeout=0.1):
            error_text = self.migration_error_dialog.read_error_text()
            raise TransferFlowError(f'Migration failed: "Something went wrong" appeared -- {error_text}')

    def start_transfer(self, screen_timeout: float = 300.0, progress_screen_timeout: float = 30.0) -> None:
        """Waits up to screen_timeout for "Your files are ready to move" -- the
        preceding "preparing your files" step can genuinely take a few minutes per its
        own on-screen text, so this defaults much longer than a normal screen
        transition -- then clicks "Bring everything over for me" to start the
        transfer, and polls up to progress_screen_timeout for "We're moving your files
        and settings" to confirm the transfer actually started. Races the
        account-mismatch confirm dialog and the close-other-apps dialog the whole time
        too (see module docstring) and clicks through either.
        """
        self.log.info('Waiting for "Your files are ready to move" (Target is preparing/scanning files)...')
        deadline = time.monotonic() + screen_timeout
        confirmed_accounts = False
        while time.monotonic() < deadline:
            self._raise_if_migration_error()
            if self.transfer_receive_screen.wait_until_showing(timeout=0.5):
                # Confirmed necessary, same reasoning as the confirm-accounts dialog:
                # check for the close-apps dialog one more time, right here, before
                # clicking -- it can appear layered over this exact screen, and a check
                # from an earlier poll cycle doesn't guarantee it's still clear now.
                while self.close_apps_dialog.accept(timeout=0.1):
                    self.log.success(
                        "\"We need to close all other applications\" appeared right "
                        "before clicking Migrate now -- clicked Close Application"
                    )
                self.log.success('Files ready to move -- starting transfer ("Bring everything over for me")')
                self.transfer_receive_screen.start_transfer()

                self.log.info('Waiting for "We\'re moving your files and settings"...')
                progress_deadline = time.monotonic() + progress_screen_timeout
                last_click = time.monotonic()
                while time.monotonic() < progress_deadline:
                    self._raise_if_migration_error()
                    if self.transfer_progress_screen.is_showing(timeout=0.5):
                        self.log.success(
                            "Transfer in progress -- \"We're moving your files and "
                            "settings\" confirmed"
                        )
                        return
                    if self.close_apps_dialog.accept(timeout=0.1):
                        self.log.success(
                            "\"We need to close all other applications\" appeared "
                            "after clicking Migrate now -- clicked Close Application"
                        )
                    elif time.monotonic() - last_click >= RECLICK_INTERVAL_SECONDS:
                        # Confirmed live (2026-10-07): the first click can report
                        # success without the button actually activating -- still on
                        # "ready to move" with nothing else blocking, so re-click it.
                        #
                        # Reported (2026-10-07): a live run went stale on this screen at
                        # 0%/0%. One re-click away from this exact check having missed
                        # the progress screen on a transient false-negative is enough to
                        # fire Migrate now again right as the real transfer is starting
                        # -- same "re-check right before acting" rule already used for
                        # the close-apps/confirm-accounts dialogs elsewhere in this file.
                        # Stop (don't click) the moment this text is confirmed, even if
                        # the check at the top of this loop iteration missed it.
                        if self.transfer_progress_screen.is_showing(timeout=0.3):
                            self.log.success(
                                "Transfer in progress -- \"We're moving your files and "
                                "settings\" confirmed right before a re-click -- not "
                                "clicking again"
                            )
                            return
                        self.log.warning(
                            "Still on \"Your files are ready to move\" -- Migrate now "
                            "may not have registered, clicking it again"
                        )
                        self.transfer_receive_screen.start_transfer()
                        last_click = time.monotonic()
                raise TransferFlowError(
                    '"We\'re moving your files and settings" never appeared within '
                    f"{progress_screen_timeout:.0f}s after clicking Migrate now"
                )
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

    def wait_for_completion(self, transfer_timeout: float = 1800.0, summary_timeout: float = 30.0) -> None:
        """Call after start_transfer() returns. Waits for "We're moving your files and
        settings" to clear (transfer finished -- defaults to 30 minutes since this is
        genuinely data-size-dependent), then checks for two confirmed-from-screenshots
        follow-on screens, each independently and optionally (neither is a required
        gate -- exact ordering between them isn't confirmed, so each is checked on its
        own rather than assuming one implies the other already appeared):

        - "Here's a summary of your migration results" -> clicks the "here" link in
          "Click here to view the details." (see MigrationSummaryScreen).
        - "We've successfully migrated your files" -> clicks "download the PDF report"
          in "You can also download the PDF report with more details." (see
          MigrationCompleteScreen).
        """
        self.log.info('Waiting for the transfer to finish ("We\'re moving your files and settings" to clear)...')
        # Confirmed live (2026-10-08): "Something went wrong" (a fatal engine error,
        # e.g. "error 2969") can appear layered over this exact screen while it's still
        # showing "0 B/s"/"...minutes left" behind it. A plain wait_until_gone() call
        # has no way to notice this -- it would just keep polling until the full
        # transfer_timeout (up to 30 minutes) and then raise a generic "did not finish"
        # error, hiding the real cause. Races the error dialog every cycle instead, same
        # pattern as every other dialog race in this file.
        #
        # Bug fixed here, confirmed via code review (2026-10-09): this loop used to
        # check `time.monotonic() < deadline` BEFORE each attempt, so it could exit
        # having made zero checks if the deadline had already passed the instant this
        # method was entered (e.g. transfer_timeout=0, or enough delay accumulated
        # earlier in the run). Restructured as a do-while so at least one full check
        # (error dialog + progress screen) always happens first, matching the
        # guarantee BaseComponent.wait_until_gone() (what this loop replaced) already
        # made.
        deadline = time.monotonic() + transfer_timeout
        finished = False
        while True:
            self._raise_if_migration_error()
            if not self.transfer_progress_screen.is_showing(timeout=0.5):
                finished = True
                break
            if time.monotonic() >= deadline:
                break
        if not finished:
            raise TransferFlowError(f"Transfer did not finish within {transfer_timeout:.0f}s")
        self.log.success("Transfer finished")

        self.log.info('Checking for "Here\'s a summary of your migration results"...')
        if self.migration_summary_screen.is_showing(timeout=summary_timeout):
            self.log.success('Migration-summary screen confirmed -- clicking "here" to view details')
            self.migration_summary_screen.click_view_details_link()
        else:
            self.log.info(
                '"Here\'s a summary of your migration results" not seen within '
                f"{summary_timeout:.0f}s -- skipping the view-details link"
            )

        self.log.info('Checking for "We\'ve successfully migrated your files"...')
        if self.migration_complete_screen.is_showing(timeout=summary_timeout):
            self.log.success(
                'Migration-complete screen confirmed -- clicking "download the PDF report"'
            )
            self.migration_complete_screen.click_download_pdf_report_link()
        else:
            self.log.info(
                '"We\'ve successfully migrated your files" not seen within '
                f"{summary_timeout:.0f}s -- skipping the PDF-report link"
            )
