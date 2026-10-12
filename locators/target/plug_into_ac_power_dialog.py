"""Locators for components.target.common_dialogs.PlugIntoAcPowerDialog ("Plug into AC
power"). Confirmed from a user-supplied screenshot (2026-10-12): a low-battery warning
-- "Be sure this PC is plugged into AC power to avoid delays while we migrate your
files and settings." -- that can appear layered over any screen during the migration,
not tied to one specific step. Has a single Cancel button.
"""

PLUG_INTO_AC_POWER_HEADING_LOCATOR = ("xpath", '//*[@Name="Plug into AC power"]')
PLUG_INTO_AC_POWER_CANCEL_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Cancel"]')
