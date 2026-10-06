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
"""

import time

from components.target.common_dialogs import CloseAppsDialog
from components.target.migration_complete_screen import MigrationCompleteScreen
from components.target.migration_summary_screen import MigrationSummaryScreen
from components.target.pairing_code_entry_screen import ConfirmAccountsDialog
from components.target.transfer_progress_screen import TransferProgressScreen
from components.target.transfer_receive_screen import TransferReceiveScreen
from factory.logger_factory import LoggerFactory


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
        self.log = LoggerFactory.get_logger("target")

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
                if not self.transfer_progress_screen.is_showing(timeout=progress_screen_timeout):
                    raise TransferFlowError(
                        '"We\'re moving your files and settings" never appeared within '
                        f"{progress_screen_timeout:.0f}s after clicking Migrate now"
                    )
                self.log.success("Transfer in progress -- \"We're moving your files and settings\" confirmed")
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
        if not self.transfer_progress_screen.wait_until_gone(timeout=transfer_timeout):
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
