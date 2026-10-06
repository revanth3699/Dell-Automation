"""Target-role "Your files are ready to move" screen -- shown after pairing succeeds
(and the account-mismatch confirm dialog, if shown, has already been accepted -- see
flows/target/pairing_flow.py's TargetPairingFlow) once Target finishes
preparing/scanning the previous PC's files. The preceding "We're preparing your files
and settings in your previous PC" screen is a pure wait, nothing to interact with --
not modeled as its own component for that reason. Confirmed from a user-supplied
screenshot (2026-10-06).
"""

from components.base_component import BaseComponent
from locators.target.transfer_receive_screen import (
    BRING_EVERYTHING_OVER_BUTTON_LOCATOR,
    FILES_READY_HEADING_LOCATOR,
)


class TransferReceiveScreen:
    def __init__(self, app_session):
        self._heading = BaseComponent(app_session, *FILES_READY_HEADING_LOCATOR, "FilesReadyHeading")
        self._bring_everything_over_button = BaseComponent(
            app_session, *BRING_EVERYTHING_OVER_BUTTON_LOCATOR, "BringEverythingOverButton"
        )

    def wait_until_showing(self, timeout: float) -> bool:
        return self._heading.exists(timeout=timeout)

    def start_transfer(self) -> None:
        """Clicks the default "Bring everything over for me" option. Choosing specific
        files/categories instead ("Let me choose what to move") is a different, not yet
        automated path."""
        self._bring_everything_over_button.click()
