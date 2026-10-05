"""Locators for components.target.common_dialogs.SignInWaitingModal ("Sign in to MyDell
to continue" / "Waiting for sign-in..." modal, shown in the app while the external
browser-based sign-in is in progress). Heading text confirmed from the project's original
reference walkthrough; the Cancel button's exact accessible name is NOT yet confirmed live
-- inferred from its visible label only. Confirm/adjust once hit for real.
"""

SIGN_IN_WAITING_HEADING_LOCATOR = ("xpath", '//*[@Name="Sign in to MyDell to continue"]')
SIGN_IN_WAITING_CANCEL_BUTTON_LOCATOR = ("xpath", '//*[@Name="Cancel"]')
