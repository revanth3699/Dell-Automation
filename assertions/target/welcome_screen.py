"""Assertion function for components.target.sign_in_screen.WelcomeScreen (the initial,
not-yet-signed-in "Welcome to Dell" screen). SIGN_IN_BUTTON_LOCATOR itself stays in
locators/target/welcome_screen.py -- it's a genuine click target (click_sign_in() uses
it directly), not a pure assertion locator -- this just builds the poll+assert check
around it using the common assertions/common.py methods.
"""

from assertions.common import button_exists
from locators.target.welcome_screen import SIGN_IN_BUTTON_LOCATOR


def is_showing(session, timeout: float = 1.0) -> bool:
    return button_exists(session, SIGN_IN_BUTTON_LOCATOR, "SignInButton", timeout=timeout)
