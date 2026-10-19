"""Expected heading text + locator + assertion function for
components.target.transfer_receive_screen.TransferReceiveScreen. The heading is never a
click target, so it lives here rather than in locators/ -- per explicit user direction
(2026-10-14).

Bug fixed here, confirmed via a user-supplied screenshot (2026-10-19): the heading
originally assumed from a 2026-10-06 screenshot, "Your files are ready to move", does
not match the live app -- the real heading is "We're ready to transfer your files",
with a redesigned card layout underneath ("Transfer my selections" with an estimated
time + a round arrow button, and a separate "Let me choose what to transfer" option) --
not the single "Bring everything over for me" button this screen was originally built
around. This heading mismatch meant wait_until_showing() never returned True, so
TargetTransferFlow.start_transfer() never even reached the point of trying to click
anything. Uses contains() on an apostrophe-free substring ("We're" has its own
apostrophe) rather than an exact match, same reasoning as every other
apostrophe-containing heading in this project. The button locator in
components/target/transfer_receive_screen.py has NOT yet been re-confirmed against
this new layout -- see that file's own docstring.
"""

from assertions.common import text_exists

HEADING_CONTAINS_TEXT = "ready to transfer your files"
FILES_READY_HEADING_LOCATOR = ("xpath", f'//*[contains(@Name, "{HEADING_CONTAINS_TEXT}")]')


def wait_until_showing(session, timeout: float) -> bool:
    return text_exists(session, FILES_READY_HEADING_LOCATOR, "FilesReadyHeading", timeout=timeout)
