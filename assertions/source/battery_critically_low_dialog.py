"""Expected heading text + locator + assertion function for
components.source.battery_critically_low_dialog.BatteryCriticallyLowDialog ("Your
battery is critically low." -- "You'll need to plug this PC into AC power to
continue."). Confirmed from a user-supplied screenshot (2026-10-14). Per explicit user
direction (2026-10-13), dismissed via Cancel only after a delay (same reasoning as
Target's "Plug into AC power" dialog -- see
components/source/battery_critically_low_dialog.py's own docstring). Never a click
target, so it lives here rather than in locators/ -- per explicit user direction
(2026-10-14).
"""

from assertions.common import text_exists

HEADING_TEXT = "Your battery is critically low."
BATTERY_CRITICALLY_LOW_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(session, BATTERY_CRITICALLY_LOW_HEADING_LOCATOR, "BatteryCriticallyLowHeading", timeout=timeout)
