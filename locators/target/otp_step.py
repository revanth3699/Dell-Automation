"""Locators for components.target.browser_sign_in_page.OtpStep (email-OTP two-step
verification, six single-digit boxes). Confirmed in tools/phase0_inspection_notes.md.
"""

OTP_BOX_NAMES = ["One", "Two", "Three", "Four", "Five", "Six"]
OTP_VERIFY_BUTTON_LOCATOR = ("xpath", '//*[@Name="Verify"]')


def otp_box_locator(name: str) -> tuple:
    return ("xpath", f'//*[@Name="Verify Passcode {name}"]')
