"""Expected heading text + locator + assertion function for
components.target.transfer_receive_screen.TransferReceiveScreen ("Your files are ready
to move"). Confirmed from a user-supplied screenshot (2026-10-06). The heading is never
a click target, so it lives here rather than in locators/ -- per explicit user
direction (2026-10-14).
"""

from assertions.common import text_exists

HEADING_TEXT = "Your files are ready to move"
FILES_READY_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def wait_until_showing(session, timeout: float) -> bool:
    return text_exists(session, FILES_READY_HEADING_LOCATOR, "FilesReadyHeading", timeout=timeout)
