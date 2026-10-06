"""Locators for components.target.common_dialogs.CloseAppsDialog ("We need to close all
other applications" -- shown when the app detects other running applications blocking
migration, e.g. Control Panel, a browser). Confirmed from a user-supplied screenshot
(2026-10-06).
"""

CLOSE_APPS_HEADING_LOCATOR = ("xpath", '//*[@Name="We need to close all other applications"]')
CLOSE_APPLICATION_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Close Application"]')
