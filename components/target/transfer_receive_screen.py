"""Target-role "Your files are ready to move" screen -- shown after pairing succeeds
(and the account-mismatch confirm dialog, if shown, has already been accepted -- see
flows/target/pairing_flow.py's TargetPairingFlow) once Target finishes
preparing/scanning the previous PC's files. The preceding "We're preparing your files
and settings in your previous PC" screen is a pure wait, nothing to interact with --
not modeled as its own component for that reason. Confirmed from a user-supplied
screenshot (2026-10-06).
"""

from loguru import logger

from components.base_component import BaseComponent
from locators.target.transfer_receive_screen import (
    BRING_EVERYTHING_OVER_BUTTON_LOCATOR,
    FILES_READY_HEADING_LOCATOR,
)

# The three native window-chrome buttons (confirmed live, 2026-10-06, via a raw
# //Button dump) -- excluded from the diagnostic fallback below so they never get
# mistaken for the real "Migrate now" button.
_KNOWN_CHROME_AUTOMATION_IDS = {"MinimizeButton", "MaximizeRestoreButton", "CloseButton"}


class TransferReceiveScreen:
    def __init__(self, app_session):
        self._session = app_session
        self._heading = BaseComponent(app_session, *FILES_READY_HEADING_LOCATOR, "FilesReadyHeading")
        self._bring_everything_over_button = BaseComponent(
            app_session, *BRING_EVERYTHING_OVER_BUTTON_LOCATOR, "BringEverythingOverButton"
        )

    def wait_until_showing(self, timeout: float) -> bool:
        return self._heading.exists(timeout=timeout)

    def start_transfer(self) -> None:
        """Clicks the default "Bring everything over for me" option (confirmed live,
        2026-10-06: its real accessible Name is "Migrate now" -- see the locator
        module). Choosing specific files/categories instead ("Let me choose what to
        move") is a different, not yet automated path.

        Bug fixed here, confirmed live (2026-10-06): click() (WinAppDriver's UIA
        Invoke-pattern /element/{id}/click) reported success -- no exception -- but the
        button did not actually activate. Uses click_at_center() instead (a real
        simulated mouse click at the element's screen coordinates), the standard
        workaround for a WebView2/React-rendered control whose onClick handler isn't
        wired to the accessibility Invoke action. The account-confirm dialog's
        "Continue" button is unrelated and unaffected -- confirmed working fine with
        plain click() -- this fix is scoped to this one button only.

        The locator-not-matching case from before this fix is kept as a fallback too
        (enumerate every non-chrome Button, click the one candidate if exactly one
        exists) in case the Name ever changes again.
        """
        try:
            self._bring_everything_over_button.click_at_center()
            return
        except Exception as exc:
            logger.warning(
                f"BringEverythingOverButton click_at_center failed ({exc}) -- "
                "enumerating all buttons on screen for diagnosis"
            )

        candidates = []
        for element in self._session.find_elements("xpath", "//Button"):
            try:
                automation_id = element.get_attribute("AutomationId")
            except Exception:
                automation_id = None
            if automation_id in _KNOWN_CHROME_AUTOMATION_IDS:
                continue
            try:
                text = element.get_text()
            except Exception as text_exc:
                text = f"<get_text failed: {text_exc}>"
            logger.debug(
                f"start_transfer diagnostic: Button candidate -- text={text!r} "
                f"AutomationId={automation_id!r}"
            )
            candidates.append(element)

        if len(candidates) == 1:
            logger.info("Exactly one non-chrome button found -- clicking it")
            try:
                candidates[0].click_at_center()
                return
            except Exception as exc:
                # Consistent with the primary click_at_center() attempt above: a click
                # failure here is still just "couldn't start the transfer", the same
                # family of error the RuntimeError below already describes -- fall
                # through to it instead of letting a raw exception escape uncaught
                # (this method's only caller, TargetTransferFlow.start_transfer(),
                # doesn't wrap this call either, so an uncaught exception here would
                # otherwise propagate all the way to RoleRunner.run() as a raw
                # traceback instead of a clean, diagnosable error).
                logger.warning(f"Fallback candidate click_at_center also failed ({exc})")

        raise RuntimeError(
            "Could not find the 'Bring everything over for me' / 'Migrate now' "
            f"button; {len(candidates)} non-chrome button candidate(s) logged above "
            "for diagnosis"
        )
