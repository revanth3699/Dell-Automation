"""Locators for components.target.sign_in_screen.WelcomeBackScreen ("Welcome back, <name>"
screen shown when the app silently refreshes a cached login). Confirmed via a user-supplied
screenshot, 2026-10-05.
"""

WELCOME_BACK_HEADING_LOCATOR = ("xpath", '//*[contains(@Name, "Welcome back")]')
# Same accessible name observed on the initial "Welcome to Dell" screen's circular arrow
# button in testing to date -- not yet independently confirmed live on this specific
# "Welcome back" variant of the screen. Confirm/adjust once hit for real.
GET_STARTED_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Continue"]')
