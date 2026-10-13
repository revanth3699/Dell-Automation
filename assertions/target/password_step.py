"""Assertion function for components.target.browser_sign_in_page.PasswordStep.
PASSWORD_FIELD_LOCATOR itself stays in locators/target/password_step.py -- it's a
genuine action target (typed into by submit()), not a pure assertion locator -- this
just builds the poll+assert check around it using the common assertions/common.py
methods.
"""

from assertions.common import text_exists
from locators.target.password_step import PASSWORD_FIELD_LOCATOR


def is_showing(session, timeout: float = 3.0) -> bool:
    return text_exists(session, PASSWORD_FIELD_LOCATOR, "PasswordField", timeout=timeout)
