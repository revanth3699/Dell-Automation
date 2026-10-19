"""Expected heading text + locator + assertion function for
components.target.common_dialogs.OtherPcNetworkDisconnectedDialog ("The other PC isn't
connected to a network."). Confirmed from a user-supplied screenshot (2026-10-12),
shown layered over the transfer-progress screen. Distinct from
NetworkDisconnectedDialog ("This PC isn't connected to a network."), which is about
THIS machine's own connectivity. Never a click target, so it lives here rather than in
locators/ -- per explicit user direction (2026-10-14).
"""

from assertions.common import text_exists

HEADING_TEXT = "It looks like your network has been disconnected"
OTHER_PC_NETWORK_DISCONNECTED_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(
        session, OTHER_PC_NETWORK_DISCONNECTED_HEADING_LOCATOR, "OtherPcNetworkDisconnectedHeading", timeout=timeout
    )
