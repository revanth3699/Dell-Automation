"""Locators for components.target.browser_sign_in_page.OtpStep (email-OTP two-step
verification, six single-digit boxes). Box/Verify locators confirmed in
tools/phase0_inspection_notes.md. The Cancel button (below Verify on the OTP page itself,
confirmed to exist directly by the user, 2026-10-06) is the deliberate way to trigger a
real sign-in cancellation for testing -- its exact accessible name is NOT yet confirmed
live, inferred from its visible label only.
"""

OTP_BOX_NAMES = ["One", "Two", "Three", "Four", "Five", "Six"]
OTP_VERIFY_BUTTON_LOCATOR = ("xpath", '//*[@Name="Verify"]')
OTP_CANCEL_BUTTON_LOCATOR = ("xpath", '//*[@Name="Cancel"]')


def otp_box_locator(name: str) -> tuple:
    return ("xpath", f'//*[@Name="Verify Passcode {name}"]')
