"""Target-role "We're moving your files and settings" screen -- the actual
transfer-in-progress screen, shown right after clicking "Migrate now". Confirmed from a
user-supplied screenshot (2026-10-06). Confirms this screen is reached and, via
wait_until_gone(), that it eventually clears (transfer finished) -- tracking the live
percentage itself is separate, not yet built.
"""

from components.base_component import BaseComponent
from locators.target.transfer_progress_screen import MOVING_FILES_HEADING_LOCATOR


class TransferProgressScreen:
    def __init__(self, app_session):
        self._heading = BaseComponent(app_session, *MOVING_FILES_HEADING_LOCATOR, "MovingFilesHeading")

    def is_showing(self, timeout: float = 2.0) -> bool:
        return self._heading.exists(timeout=timeout)

    def wait_until_gone(self, timeout: float) -> bool:
        return self._heading.wait_until_gone(timeout=timeout)
