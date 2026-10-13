"""Expected heading text + locator + assertion function for
components.target.common_dialogs.RegionalSettingsNotSupportedDialog ("Set both of your
PCs to the same supported region"). Means Target and Source PCs are set to different,
incompatible regions -- nothing to retry, so it's treated the same terminal way as
OtherPcNetworkDisconnectedDialog. Never a click target, so it lives here rather than in
locators/ -- per explicit user direction (2026-10-14).

Bug fixed here, confirmed via a live run (2026-10-14): the first screenshot the user
shared of this dialog showed a DIFFERENT heading, "Your regional settings aren't
supported.", which this file originally used -- but the user's own original instruction
had asked to assert for "Set both of your PCs to same supported region" specifically.
A second, later live screenshot (from an actual run, not a staged one) confirmed the
heading really is "Set both of your PCs to the same supported region" -- the exact
phrase originally requested. Switched to that confirmed text; "Your regional settings
aren't supported." may be a related but distinct screen/link target (the first
screenshot's body text mentioned "Here's how", a link this dialog doesn't have) and is
not asserted on here.
"""

from assertions.common import text_exists

HEADING_TEXT = "Set both of your PCs to the same supported region"
REGIONAL_SETTINGS_NOT_SUPPORTED_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(
        session,
        REGIONAL_SETTINGS_NOT_SUPPORTED_HEADING_LOCATOR,
        "RegionalSettingsNotSupportedHeading",
        timeout=timeout,
    )
