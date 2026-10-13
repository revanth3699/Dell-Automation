"""TargetTransferFlow: starts the file transfer once pairing has succeeded.

Confirmed from a user-supplied screenshot (2026-10-06): after pairing, the app shows
"We're preparing your files and settings in your previous PC" (can genuinely take a
few minutes per its own on-screen text), then "Your files are ready to move".
start_transfer() waits for that second screen and clicks the default "Bring everything
over for me" option.

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
clicking "Migrate now" -- not just relying on the background race above.

Confirmed from a user-supplied screenshot (2026-10-06): after that click, "We're moving
your files and settings" (the actual transfer-progress screen) appears. start_transfer()
now polls for it to confirm the transfer genuinely started.

Bug fixed here, confirmed live (2026-10-06): the close-apps dialog can ALSO appear
AFTER clicking Migrate now, layered over "Your files are ready to move" while waiting
for "We're moving your files and settings" to show up. Now races the close-apps dialog
here too, same as everywhere else.

Bug fixed here, confirmed live (2026-10-07): click_at_center() on "Migrate now"
reported success (no exception) but confirmed via screenshot that the button visually
never actually activated. Rather than trust a single click, the wait for "We're moving
your files and settings" now periodically re-clicks "Migrate now" (every
RECLICK_INTERVAL_SECONDS) for as long as neither it nor the close-apps dialog has
appeared.

Bug fixed here, confirmed live (2026-10-08): a fatal engine-side error ("Something went
wrong ... (error 2969). Please close and try again.") can appear layered over the
transfer-progress screen mid-transfer. All three wait loops in this file
(start_transfer()'s two, wait_for_completion()'s one) race the migration-error
assertion every cycle and raise immediately with the real error text if it appears,
same pattern as every other dialog race here.

Per explicit user direction (2026-10-14): this file holds no existence-check locators.
Every is_X_showing()/is_X_confirmed() assertion is imported directly from
assertions/target/<name>.py and called with the raw app_session; components/target/ now
holds only click/type actions, called only after the matching assertion confirms
presence.
"""

import time

from components.target.common_dialogs import (
    CloseAppsDialog,
    DesktopShortcutDialog,
    MigrationErrorDialog,
    OtherPcNetworkDisconnectedDialog,
    PlugIntoAcPowerDialog,
)
from components.target.migration_complete_screen import MigrationCompleteScreen
from components.target.migration_summary_screen import MigrationSummaryScreen
from components.target.pairing_code_entry_screen import ConfirmAccountsDialog
from components.target.sign_in_screen import WelcomeBackScreen
from components.target.transfer_receive_screen import TransferReceiveScreen
from assertions.target import (
    confirm_accounts_dialog as confirm_accounts_assertions,
    close_apps_dialog as close_apps_assertions,
    desktop_shortcut_dialog as desktop_shortcut_assertions,
    migration_complete_screen as migration_complete_assertions,
    migration_error_dialog as migration_error_assertions,
    migration_summary_screen as migration_summary_assertions,
    other_pc_network_disconnected_dialog as other_pc_network_disconnected_assertions,
    plug_into_ac_power_dialog as plug_into_ac_power_assertions,
    transfer_progress_screen as transfer_progress_assertions,
    transfer_receive_screen as transfer_receive_assertions,
    welcome_back_screen as welcome_back_assertions,
)
from factory.logger_factory import LoggerFactory

RECLICK_INTERVAL_SECONDS = 3.0

# Per explicit user direction (2026-10-14): clicking "download a PDF" opens the PDF file
# (in an external viewer/browser), which takes a moment -- give it time before clicking
# "Back to Home", rather than clicking through immediately.
PDF_OPEN_WAIT_SECONDS = 30.0


class TransferFlowError(Exception):
    pass


class TargetTransferFlow:
    def __init__(self, app_session):
        self.app_session = app_session
        self.transfer_receive_screen = TransferReceiveScreen(app_session)
        self.migration_summary_screen = MigrationSummaryScreen(app_session)
        self.migration_complete_screen = MigrationCompleteScreen(app_session)
        self.welcome_back_screen = WelcomeBackScreen(app_session)
        self.confirm_accounts_dialog = ConfirmAccountsDialog(app_session)
        self.close_apps_dialog = CloseAppsDialog(app_session)
        self.migration_error_dialog = MigrationErrorDialog(app_session)
        self.other_pc_network_disconnected_dialog = OtherPcNetworkDisconnectedDialog(app_session)
        self.plug_into_ac_power_dialog = PlugIntoAcPowerDialog(app_session)
        self.desktop_shortcut_dialog = DesktopShortcutDialog(app_session)
        self.log = LoggerFactory.get_logger("target")

    def _raise_if_migration_error(self) -> None:
        """Shared by every wait loop in this class (confirmed via code review,
        2026-10-09: this exact 3-line check used to be copy-pasted at three separate
        call sites). Raises TransferFlowError immediately if "Something went wrong"
        is showing; a no-op otherwise."""
        if migration_error_assertions.is_showing(self.app_session, timeout=0.1):
            error_text = self.migration_error_dialog.read_error_text()
            raise TransferFlowError(f'Migration failed: "Something went wrong" appeared -- {error_text}')

    def _raise_if_other_pc_disconnected(self) -> None:
        """Shared by every wait loop in this class, same reasoning as
        _raise_if_migration_error(). Confirmed directly by the user via a live
        screenshot (2026-10-12): "The other PC isn't connected to a network." means the
        Source PC lost its network connection -- nothing Target can retry locally, so
        per explicit user direction this clicks "Cancel transfer" and raises
        immediately, aborting the run. The caller's own Session.close() (already wired
        in orchestration/role_runner.py's TargetRunner.run(), via its finally block)
        is what then actually closes the app and WinAppDriver -- same cleanup path
        every other failure in this flow already goes through, nothing extra needed
        here."""
        if other_pc_network_disconnected_assertions.is_showing(self.app_session, timeout=0.1):
            self.log.error(
                '"The other PC isn\'t connected to a network." appeared -- clicking '
                '"Cancel transfer" and aborting'
            )
            self.other_pc_network_disconnected_dialog.cancel_transfer()
            raise TransferFlowError(
                'Migration failed: "The other PC isn\'t connected to a network." appeared -- '
                "the Source PC lost network connectivity mid-transfer; clicked Cancel transfer"
            )

    def _accept_plug_into_ac_power_if_showing(self) -> bool:
        """Shared by every wait loop in this class, same reasoning as
        _raise_if_migration_error(). Confirmed directly by the user via a live
        screenshot (2026-10-12): "Plug into AC power" (a low-battery warning) can
        appear layered over any screen during the migration -- transfer is the
        longest-running wait in this whole flow (up to 30 minutes), so the most likely
        place to actually hit a real low-battery condition. Not fatal -- clicks Cancel
        (after PlugIntoAcPowerDialog's own 15s wait) and lets the caller's loop
        continue."""
        if plug_into_ac_power_assertions.is_showing(self.app_session, timeout=0.1):
            self.plug_into_ac_power_dialog.click_cancel()
            self.log.warning('"Plug into AC power" appeared -- waited and clicked Cancel')
            return True
        return False

    def _accept_desktop_shortcut_if_showing(self) -> bool:
        """Confirmed directly by the user via a live screenshot (2026-10-13): "Add a
        desktop shortcut before you go" -- its own wording places it near the very end
        of the flow, so this is only raced in wait_for_completion()'s final
        home-confirmation wait, not every loop in this file (unlike
        _accept_plug_into_ac_power_if_showing(), which can genuinely appear anywhere).
        Not fatal -- clicks "Create shortcut" per explicit user direction and lets the
        caller's loop continue."""
        if desktop_shortcut_assertions.is_showing(self.app_session, timeout=0.1):
            self.desktop_shortcut_dialog.click_create_shortcut()
            self.log.success(
                '"Add a desktop shortcut before you go" appeared -- clicked "Create shortcut"'
            )
            return True
        return False

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
            self._raise_if_other_pc_disconnected()
            if self._accept_plug_into_ac_power_if_showing():
                continue
            if transfer_receive_assertions.wait_until_showing(self.app_session, timeout=0.5):
                # Confirmed necessary, same reasoning as the confirm-accounts dialog:
                # check for the close-apps dialog one more time, right here, before
                # clicking -- it can appear layered over this exact screen, and a check
                # from an earlier poll cycle doesn't guarantee it's still clear now.
                while close_apps_assertions.is_showing(self.app_session, timeout=0.1):
                    self.close_apps_dialog.click_close_application()
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
                    self._raise_if_other_pc_disconnected()
                    if self._accept_plug_into_ac_power_if_showing():
                        continue
                    if transfer_progress_assertions.is_showing(self.app_session, timeout=0.5):
                        self.log.success(
                            "Transfer in progress -- \"We're moving your files and "
                            "settings\" confirmed"
                        )
                        return
                    if close_apps_assertions.is_showing(self.app_session, timeout=0.1):
                        self.close_apps_dialog.click_close_application()
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
                        if transfer_progress_assertions.is_showing(self.app_session, timeout=0.3):
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
            if not confirmed_accounts and confirm_accounts_assertions.is_showing(self.app_session, timeout=0.1):
                self.confirm_accounts_dialog.click_continue()
                self.log.success(
                    "Account-mismatch confirm dialog appeared during the "
                    "preparing-files wait -- clicked Continue"
                )
                confirmed_accounts = True
            if close_apps_assertions.is_showing(self.app_session, timeout=0.1):
                self.close_apps_dialog.click_close_application()
                self.log.success(
                    "\"We need to close all other applications\" appeared -- clicked "
                    "Close Application"
                )
        raise TransferFlowError(
            f'"Your files are ready to move" screen never appeared within {screen_timeout:.0f}s'
        )

    def wait_for_completion(
        self,
        transfer_timeout: float = 1800.0,
        summary_timeout: float = 30.0,
        complete_timeout: float = 30.0,
        home_timeout: float = 30.0,
    ) -> None:
        """Call after start_transfer() returns. Waits for "We're moving your files and
        settings" to clear (transfer finished -- defaults to 30 minutes since this is
        genuinely data-size-dependent), then drives the real, confirmed completion
        sequence:

        "Here's a summary of your migration results" -> click "Finish" (top right, NOT
        the "here" link) -> "Your migration is now complete" -> click "download a PDF",
        then click "Back to Home" -> back on the Welcome-back home screen, confirmed via
        its "Sign Out" button. "Add a desktop shortcut before you go" is raced during
        this final wait too -- confirmed to appear near the very end of the flow.

        Every step here is now a required gate (raises TransferFlowError if a screen
        doesn't appear in time), not optional. Once is_home_confirmed() returns True,
        this method returns normally; the caller's own Session.close() (already wired
        in orchestration/role_runner.py's TargetRunner.run(), via its finally block) is
        what actually closes the app.
        """
        self.log.info('Waiting for the transfer to finish ("We\'re moving your files and settings" to clear)...')
        # Confirmed live (2026-10-08): "Something went wrong" (a fatal engine error,
        # e.g. "error 2969") can appear layered over this exact screen while it's still
        # showing "0 B/s"/"...minutes left" behind it. Races the error dialog every
        # cycle instead, same pattern as every other dialog race in this file.
        #
        # Bug fixed here, confirmed via code review (2026-10-09): this loop used to
        # check `time.monotonic() < deadline` BEFORE each attempt, so it could exit
        # having made zero checks if the deadline had already passed the instant this
        # method was entered. Restructured as a do-while so at least one full check
        # always happens first.
        deadline = time.monotonic() + transfer_timeout
        finished = False
        while True:
            self._raise_if_migration_error()
            self._raise_if_other_pc_disconnected()
            if self._accept_plug_into_ac_power_if_showing():
                continue
            if not transfer_progress_assertions.is_showing(self.app_session, timeout=0.5):
                finished = True
                break
            if time.monotonic() >= deadline:
                break
        if not finished:
            raise TransferFlowError(f"Transfer did not finish within {transfer_timeout:.0f}s")
        self.log.success("Transfer finished")

        self.log.info('Waiting for "Here\'s a summary of your migration results"...')
        if not migration_summary_assertions.is_showing(self.app_session, timeout=summary_timeout):
            raise TransferFlowError(
                f'"Here\'s a summary of your migration results" never appeared within '
                f"{summary_timeout:.0f}s after the transfer finished"
            )
        self.log.success('Migration-summary screen confirmed -- clicking "Finish"')
        self.migration_summary_screen.click_finish()

        self.log.info('Waiting for "Your migration is now complete"...')
        if not migration_complete_assertions.is_showing(self.app_session, timeout=complete_timeout):
            raise TransferFlowError(
                f'"Your migration is now complete" never appeared within {complete_timeout:.0f}s '
                "after clicking Finish"
            )
        self.log.success(
            'Migration-complete screen confirmed -- clicking "download a PDF", then "Back to Home"'
        )
        self.migration_complete_screen.click_download_pdf_link()
        self.log.info(f"Waiting {PDF_OPEN_WAIT_SECONDS:.0f}s for the downloaded PDF to open...")
        time.sleep(PDF_OPEN_WAIT_SECONDS)
        self.migration_complete_screen.click_back_to_home()

        self.log.info('Confirming return to the home screen ("Sign Out" visible)...')
        # Bug fixed here, confirmed directly by the user via a live screenshot
        # (2026-10-13): "Add a desktop shortcut before you go" can appear layered over
        # this exact wait -- a plain single is_home_confirmed() call had no way to
        # notice or click through it, so it would just burn the whole home_timeout.
        # Restructured as an explicit poll loop (do-while, same reasoning as
        # wait_for_completion()'s transfer-finished wait above) that races it every
        # cycle, same pattern as every other dialog race in this file.
        deadline = time.monotonic() + home_timeout
        home_confirmed = False
        while True:
            if self._accept_desktop_shortcut_if_showing():
                continue
            if welcome_back_assertions.is_home_confirmed(self.app_session, timeout=0.5):
                home_confirmed = True
                break
            if time.monotonic() >= deadline:
                break
        if not home_confirmed:
            raise TransferFlowError(
                f"Did not confirm return to the home screen within {home_timeout:.0f}s "
                "after clicking Back to Home"
            )
        self.log.success("Confirmed back on the home screen -- migration flow complete")
