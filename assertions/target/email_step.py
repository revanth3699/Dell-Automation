"""Assertion function for components.target.browser_sign_in_page.EmailStep.
EMAIL_FIELD_LOCATOR itself stays in locators/target/email_step.py -- it's a genuine
action target (typed into by submit()), not a pure assertion locator -- this just
builds the poll+assert check around it using the common assertions/common.py methods.
"""

from assertions.common import text_exists
from locators.target.email_step import EMAIL_FIELD_LOCATOR


def is_showing(session, timeout: float = 3.0) -> bool:
    return text_exists(session, EMAIL_FIELD_LOCATOR, "EmailField", timeout=timeout)
