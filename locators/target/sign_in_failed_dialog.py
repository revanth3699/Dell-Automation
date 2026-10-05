"""Locators for components.target.common_dialogs.SignInFailedDialog ("There was a
problem signing in" / "Sign-in failed. Please try again." dialog). Confirmed from
"dell screens flow.pdf" (2026-10-05): has a Cancel and a Retry button.
"""

SIGN_IN_FAILED_HEADING_LOCATOR = ("xpath", '//*[@Name="There was a problem signing in"]')
SIGN_IN_FAILED_RETRY_BUTTON_LOCATOR = ("xpath", '//*[@Name="Retry"]')
