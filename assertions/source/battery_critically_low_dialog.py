"""Expected heading text + locator + assertion function for
components.source.battery_critically_low_dialog.BatteryCriticallyLowDialog ("Your
battery is critically low." -- "You'll need to plug this PC into AC power to
continue."). Confirmed from a user-supplied screenshot (2026-10-14). Distinct from
Target's "Plug into AC power" (a low-battery warning, waited out before clicking
Cancel) -- this one is "critically low", not just a warning, so per explicit user
direction it's dismissed immediately, no wait first. Never a click target, so it lives
here rather than in locators/ -- per explicit user direction (2026-10-14).
"""

from assertions.common import text_exists

HEADING_TEXT = "Your battery is critically low."
BATTERY_CRITICALLY_LOW_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(session, BATTERY_CRITICALLY_LOW_HEADING_LOCATOR, "BatteryCriticallyLowHeading", timeout=timeout)
