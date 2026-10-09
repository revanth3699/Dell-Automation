"""Locators for components.target.sign_in_screen.WelcomeBackScreen ("Welcome back, <name>"
screen shown when the app silently refreshes a cached login). Confirmed via a user-supplied
screenshot, 2026-10-05.
"""

WELCOME_BACK_HEADING_LOCATOR = ("xpath", '//*[contains(@Name, "Welcome back")]')
# Same accessible name observed on the initial "Welcome to Dell" screen's circular arrow
# button in testing to date -- not yet independently confirmed live on this specific
# "Welcome back" variant of the screen. Confirm/adjust once hit for real.
GET_STARTED_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Continue"]')

# Confirmed directly by the user (2026-10-09) via a live screenshot: after a full
# migration completes and "Back to Home" is clicked
# (components/target/migration_complete_screen.py), this same Welcome-back screen
# reappears, with this exact bullet text visible -- used as the confirmation that
# we're genuinely back on the home screen post-migration, not just that the heading
# happens to match.
NOTHING_LOST_TEXT_LOCATOR = ("xpath", '//*[@Name="Nothing\'s lost from your old PC"]')
