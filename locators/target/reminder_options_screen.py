"""Locators for components.target.reminder_options_screen.ReminderOptionsScreen --
click-target locators only. The heading assertion locator lives in
assertions/target/reminder_options_screen.py instead.

Confirmed from user-supplied screenshots (2026-10-19): radio options "Tonight"/
"Tomorrow"/"Next week", "Set reminder" button. Radio control type not confirmed from the
live UIA tree (generic wildcard tag, per CLAUDE.md's gotcha); "Set reminder" uses Button,
consistent with every other primary call-to-action in this app being confirmed as Button
control type, though this specific one hasn't been independently confirmed.
"""

TONIGHT_OPTION_LOCATOR = ("xpath", '//*[@Name="Tonight"]')
TOMORROW_OPTION_LOCATOR = ("xpath", '//*[@Name="Tomorrow"]')
NEXT_WEEK_OPTION_LOCATOR = ("xpath", '//*[@Name="Next week"]')
SET_REMINDER_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Set reminder"]')
