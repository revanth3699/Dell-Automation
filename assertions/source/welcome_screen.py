"""Assertion function for components.source.welcome_screen.WelcomeScreen ("Welcome to
Dell Migrate."). LETS_GET_STARTED_BUTTON_LOCATOR itself stays in
locators/source/welcome_screen.py -- it's a genuine click target
(click_get_started() uses it directly), not a pure assertion locator -- this just
builds the poll+assert check around it using the common assertions/common.py methods.
"""

from assertions.common import button_exists
from locators.source.welcome_screen import LETS_GET_STARTED_BUTTON_LOCATOR


def is_showing(session, timeout: float = 1.0) -> bool:
    return button_exists(session, LETS_GET_STARTED_BUTTON_LOCATOR, "LetsGetStartedButton", timeout=timeout)
