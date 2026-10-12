"""Locators for components.target.sign_in_screen.WelcomeBackScreen ("Welcome back, <name>"
screen shown when the app silently refreshes a cached login). Confirmed via a user-supplied
screenshot, 2026-10-05.
"""

WELCOME_BACK_HEADING_LOCATOR = ("xpath", '//*[contains(@Name, "Welcome back")]')
# Same accessible name observed on the initial "Welcome to Dell" screen's circular arrow
# button in testing to date -- not yet independently confirmed live on this specific
# "Welcome back" variant of the screen. Confirm/adjust once hit for real.
GET_STARTED_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Continue"]')

# Bug fixed here, confirmed directly by the user via a live run (2026-10-13): the
# "Nothing's lost from your old PC" bullet text this used to check for timed out
# (exists check False after 30s) on a real post-migration run -- the text isn't a
# reliable signal in practice. Replaced with the "Sign Out" button/link (top of this
# screen, confirmed via a user-supplied screenshot) as the real confirmation that
# we're genuinely back on the home screen post-migration, not just that the heading
# happens to match.
SIGN_OUT_BUTTON_LOCATOR = ("xpath", '//*[@Name="Sign Out"]')
