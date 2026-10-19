"""Locators for components.target.common_dialogs.CloseAppsDialog -- click-target
locator only. The heading assertion locator lives in
assertions/target/close_apps_dialog.py instead.

Bug fixed here, confirmed via a user-supplied screenshot (2026-10-19): the button is
actually named "Close applications" (plural), not "Close Application" -- the real
dialog, "Close other applications", has a "Cancel transfer" and a "Close applications"
button.
"""

CLOSE_APPLICATION_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Close applications"]')
