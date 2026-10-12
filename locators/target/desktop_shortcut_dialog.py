"""Locators for components.target.common_dialogs.DesktopShortcutDialog ("Add a desktop
shortcut before you go"). Confirmed from a user-supplied screenshot (2026-10-13) --
its own "before you go" wording places it near the very end of the Target flow,
offering to create a desktop shortcut back into the app via SupportAssist, with
"No, thanks" and "Create shortcut" buttons.
"""

DESKTOP_SHORTCUT_HEADING_LOCATOR = ("xpath", '//*[@Name="Add a desktop shortcut before you go"]')
CREATE_SHORTCUT_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Create shortcut"]')
