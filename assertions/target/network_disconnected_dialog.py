"""Expected heading text + locator + assertion function for
components.target.common_dialogs.NetworkDisconnectedDialog ("This PC isn't connected to
a network."). Confirmed from two user-supplied screenshots (2026-10-09), each showing
the dialog layered over a different underlying screen. Never a click target, so it
lives here rather than in locators/ -- per explicit user direction (2026-10-14).
"""

from assertions.common import text_exists

HEADING_TEXT = "Connect this PC to a trusted network"
NETWORK_DISCONNECTED_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(session, NETWORK_DISCONNECTED_HEADING_LOCATOR, "NetworkDisconnectedHeading", timeout=timeout)
