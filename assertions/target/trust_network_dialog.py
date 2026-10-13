"""Expected heading text + locator + assertion function for
components.target.common_dialogs.TrustNetworkDialog ("Connect to a trusted network"
dialog, confirmed appearing after sign-in). Never a click target, so it lives here
rather than in locators/ -- per explicit user direction (2026-10-14).

Simplified here, per earlier explicit user direction (2026-10-07): checks the dialog's
own heading rather than the button directly -- the button can be visible but disabled
while the dialog shows "Trusting this network..." mid-transition (confirmed via a live
screenshot showing both Cancel and Trust Network greyed out during that moment), so
finding it existing wasn't the same as it actually being clickable.
"""

from assertions.common import text_exists

HEADING_TEXT = "Connect to a trusted network"
TRUST_NETWORK_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, TRUST_NETWORK_HEADING_LOCATOR, "TrustNetworkHeading", timeout=timeout)
