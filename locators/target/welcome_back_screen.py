"""Locators for components.target.sign_in_screen.WelcomeBackScreen -- click-target
locators only. The heading and "Sign Out" assertion locators live in
assertions/target/welcome_back_screen.py instead (never click targets).
"""

# Same accessible name observed on the initial "Welcome to Dell" screen's circular arrow
# button in testing to date -- not yet independently confirmed live on this specific
# "Welcome back" variant of the screen. Confirm/adjust once hit for real.
GET_STARTED_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Continue"]')

# Confirmed from a user-supplied screenshot (2026-10-19): a second action on this same
# screen, next to the "Ready to get started?" panel -- defers the migration instead of
# continuing. Control type not confirmed from the live UIA tree (only visually, from the
# screenshot, as blue link-styled text) -- generic wildcard tag until confirmed live, per
# CLAUDE.md's gotcha about not assuming control type from visual style alone.
REMIND_ME_LATER_LOCATOR = ("xpath", '//*[@Name="Remind me later."]')
