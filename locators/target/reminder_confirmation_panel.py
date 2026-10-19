"""Locators for components.target.reminder_confirmation_panel.ReminderConfirmationPanel
-- click-target locator only. The heading assertion locator lives in
assertions/target/reminder_confirmation_panel.py instead.

Confirmed from a user-supplied screenshot (2026-10-19): per the user's own description,
clicking this actually closes the application, not just the panel. Control type not
confirmed from the live UIA tree -- generic wildcard tag, per CLAUDE.md's gotcha.
"""

CLOSE_BUTTON_LOCATOR = ("xpath", '//*[@Name="Close"]')
