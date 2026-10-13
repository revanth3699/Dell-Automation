"""Expected heading text + locator + assertion function for
components.source.regional_settings_not_supported_dialog.RegionalSettingsNotSupportedDialog
("Your regional settings aren't supported." -- "To continue, you'll need to update to
a supported region. Here's how."). Confirmed from a user-supplied screenshot
(2026-10-14).

Fatal on Source: per explicit user direction, clicking its "Close" button closes the
app entirely -- there is nothing to retry locally. Raced continuously (same "race it
continuously" pattern as every other unpredictable dialog in this project) and raises
immediately once confirmed -- see flows/source/common_dialogs.py's
raise_if_regional_settings_not_supported().

Never a click target, so it lives here rather than in locators/ -- per explicit user
direction (2026-10-14).
"""

from assertions.common import text_exists

HEADING_TEXT = "Your regional settings aren't supported."
REGIONAL_SETTINGS_NOT_SUPPORTED_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(
        session, REGIONAL_SETTINGS_NOT_SUPPORTED_HEADING_LOCATOR, "RegionalSettingsNotSupportedHeading", timeout=timeout
    )
