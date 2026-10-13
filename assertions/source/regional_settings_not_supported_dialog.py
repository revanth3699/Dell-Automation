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

Bug fixed here, confirmed via a live run (2026-10-14): the original locator did an
exact @Name="Your regional settings aren't supported." match -- the apostrophe in
"aren't" hit this project's own documented curly-vs-straight-apostrophe trap (see
CLAUDE.md's Gotchas section and assertions/target/sign_in_failed_dialog.py's history),
so is_showing() returned False forever against a screen genuinely on screen (confirmed
live via a user-supplied screenshot showing the dialog present while the log showed
nothing but repeated False checks). Replaced with contains() on an apostrophe-free,
distinctive substring, same fix pattern as every other apostrophe-containing heading in
this project.
"""

from assertions.common import text_exists

# Apostrophe-free substring of "Your regional settings aren't supported." -- avoids the
# exact-match apostrophe-mismatch trap (see module docstring above).
HEADING_CONTAINS_TEXT = "Your regional settings"
REGIONAL_SETTINGS_NOT_SUPPORTED_HEADING_LOCATOR = ("xpath", f'//*[contains(@Name, "{HEADING_CONTAINS_TEXT}")]')


def is_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(
        session, REGIONAL_SETTINGS_NOT_SUPPORTED_HEADING_LOCATOR, "RegionalSettingsNotSupportedHeading", timeout=timeout
    )
