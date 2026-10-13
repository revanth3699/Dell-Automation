"""Locators for components.target.sign_in_screen.WelcomeBackScreen -- click-target
locator only. The heading and "Sign Out" assertion locators live in
assertions/target/welcome_back_screen.py instead (never click targets).
"""

# Same accessible name observed on the initial "Welcome to Dell" screen's circular arrow
# button in testing to date -- not yet independently confirmed live on this specific
# "Welcome back" variant of the screen. Confirm/adjust once hit for real.
GET_STARTED_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Continue"]')
