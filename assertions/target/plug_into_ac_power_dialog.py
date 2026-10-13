"""Expected heading text + locator + assertion function for
components.target.common_dialogs.PlugIntoAcPowerDialog ("Plug into AC power").
Confirmed from a user-supplied screenshot (2026-10-12). Never a click target, so it
lives here rather than in locators/ -- per explicit user direction (2026-10-14).
"""

from assertions.common import text_exists

HEADING_TEXT = "Plug into AC power"
PLUG_INTO_AC_POWER_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(session, PLUG_INTO_AC_POWER_HEADING_LOCATOR, "PlugIntoAcPowerHeading", timeout=timeout)
