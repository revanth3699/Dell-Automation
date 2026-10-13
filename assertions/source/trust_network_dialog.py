"""Expected heading text + locator + assertion function for
components.source.trust_network_dialog.TrustNetworkDialog ("Do you trust the <network>
network?"). Confirmed live (2026-10-07). Never a click target, so it lives here rather
than in locators/ -- per explicit user direction (2026-10-14).
"""

from assertions.common import text_exists

HEADING_CONTAINS_TEXT = "Do you trust the"
HEADING_LOCATOR = ("xpath", f'//*[contains(@Name, "{HEADING_CONTAINS_TEXT}")]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, HEADING_LOCATOR, "TrustNetworkHeading", timeout=timeout)
