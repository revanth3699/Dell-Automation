"""Assertion function for components.target.browser_sign_in_page.OtpStep. The box
locator itself stays in locators/target/otp_step.py -- it's a genuine action target
(typed into by submit()), not a pure assertion locator -- this just builds the
poll+assert check around the first box using the common assertions/common.py methods.
"""

from assertions.common import text_exists
from locators.target.otp_step import OTP_BOX_NAMES, otp_box_locator


def is_showing(session, timeout: float = 2.0) -> bool:
    """Checks the first box only (same as the component's own original boxes[0]
    check) -- if the first exists, the page is showing."""
    return text_exists(session, otp_box_locator(OTP_BOX_NAMES[0]), "OtpBoxOne", timeout=timeout)
