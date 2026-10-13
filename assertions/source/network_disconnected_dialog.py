"""Expected heading text + locator + assertion function for
components.source.network_disconnected_dialog.NetworkDisconnectedDialog. Same generic
connectivity-check modal as assertions/target/network_disconnected_dialog.py -- confirmed
from the same user-supplied screenshots (2026-10-09). Never a click target, so it lives
here rather than in locators/ -- per explicit user direction (2026-10-14).
"""

from assertions.common import text_exists

HEADING_TEXT = "This PC isn't connected to a network."
HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(session, HEADING_LOCATOR, "NetworkDisconnectedHeading", timeout=timeout)
