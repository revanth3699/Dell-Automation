"""Locators for components.target.browser_sign_in_page.EmailStep.

Inferred from a reference screenshot only, not yet independently confirmed live -- the
test browser profile has consistently retained an existing session across test runs so
far, so this step has never actually been exercised. Confirm/adjust once hit for real.
"""

EMAIL_FIELD_LOCATOR = ("xpath", '//Edit[@Name="Email or Mobile Number"]')
EMAIL_CONTINUE_BUTTON_LOCATOR = ("xpath", '//*[@Name="Continue"]')
