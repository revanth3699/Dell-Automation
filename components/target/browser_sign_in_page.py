"""
Browser-hosted Dell sign-in page elements for the Target PC flow (Target-only: Source PC
has no authentication step). This is the externally-opened OS-default browser, not the
app window -- email, password, and email-OTP two-step verification steps, plus the
Chrome "Restore pages?" crash-recovery dialog that can interrupt any of them. Confirmed
via live testing; see PROJECT_PLAN.md Sec 5.3c and tools/phase0_inspection_notes.md.

Email/password locators are inferred from a reference screenshot only, not yet
independently confirmed live -- the test browser profile has consistently retained an
existing session across test runs so far, so these two steps have never actually been
exercised. Flagged here, not assumed silently -- confirm/adjust once hit for real.

Error-banner text and the account-lockout wording below are confirmed from a
user-supplied flow diagram/screenshot set (dell screens flow.pdf, 2026-10-05), not yet
independently confirmed live.
"""

from components.base_component import BaseComponent
from locators.target.email_step import EMAIL_CONTINUE_BUTTON_LOCATOR, EMAIL_FIELD_LOCATOR
from locators.target.error_banner import ERROR_BANNER_LOCATOR
from locators.target.otp_step import OTP_BOX_NAMES, OTP_VERIFY_BUTTON_LOCATOR, otp_box_locator
from locators.target.password_step import PASSWORD_FIELD_LOCATOR, PASSWORD_SIGNIN_BUTTON_LOCATOR
from locators.target.restore_pages_dialog import RESTORE_PAGES_CLOSE_BUTTON_LOCATOR


class RestorePagesDialog:
    """Chrome's "Chrome didn't shut down correctly" restore-pages dialog -- appears
    unpredictably whenever the browser process was previously force-killed (which our
    own cleanup between test runs does). Confirmed to steal keyboard focus mid-typing if
    it pops up while a flow step is in progress, truncating whatever was being typed --
    dismiss defensively at the points this has actually been observed (right after
    attach, and again at the password -> OTP page transition).
    """

    def __init__(self, browser_session):
        # Deliberately scoped to ImageButton specifically -- a bare //*[@Name="Close"]
        # would match the window's own WindowsCaptionButton "Close" FIRST (closing the
        # whole browser), since find_element returns the first document-order match.
        self._close_button = BaseComponent(
            browser_session, *RESTORE_PAGES_CLOSE_BUTTON_LOCATOR, "RestorePagesCloseButton", timeout=1.5
        )

    def dismiss_if_present(self) -> None:
        if self._close_button.exists(timeout=1.5):
            self._close_button.click()


class EmailStep:
    def __init__(self, browser_session):
        self._field = BaseComponent(browser_session, *EMAIL_FIELD_LOCATOR, "EmailField", timeout=3.0)
        self._continue_button = BaseComponent(browser_session, *EMAIL_CONTINUE_BUTTON_LOCATOR, "EmailContinueButton")
        self._error_banner = BaseComponent(browser_session, *ERROR_BANNER_LOCATOR, "EmailErrorBanner", timeout=8.0)

    def is_showing(self, timeout: float = 3.0) -> bool:
        return self._field.exists(timeout=timeout)

    def submit(self, username: str, attempts: int = 3, advance_timeout: float = 15.0) -> bool:
        """Types the email and clicks Continue, then waits for the field to actually
        disappear (confirming the page advanced) before returning -- confirmed via live
        testing this step's click can silently not register even though the WinAppDriver
        call itself returns success, same class of flakiness already handled for the OTP
        step. Retries the whole type+click up to `attempts` times if the field is still
        there. Returns whether it ultimately advanced.
        """
        for attempt in range(attempts):
            self._field.type_text(username)
            self._continue_button.click()
            if self._field.wait_until_gone(timeout=advance_timeout):
                return True
        return False

    def submit_and_expect_error(self, wrong_username: str, timeout: float = 8.0) -> bool:
        """Negative-path check: types a deliberately wrong value, clicks Continue ONCE,
        and returns whether the "unable to match the details" error banner appeared.
        Deliberately does not retry like submit() does -- unlike a flaky click that never
        registered, a rejected value reliably leaves this same field in place, so a retry
        loop here would just resubmit the wrong value multiple times for no benefit (and,
        on the password/OTP steps that share this same shape, would needlessly burn
        further attempts against that step's confirmed 6-attempt account lockout).
        """
        self._field.type_text(wrong_username)
        self._continue_button.click()
        return self._error_banner.exists(timeout=timeout)


class PasswordStep:
    def __init__(self, browser_session):
        self._field = BaseComponent(browser_session, *PASSWORD_FIELD_LOCATOR, "PasswordField", timeout=3.0)
        self._signin_button = BaseComponent(browser_session, *PASSWORD_SIGNIN_BUTTON_LOCATOR, "PasswordSignInButton")
        self._error_banner = BaseComponent(browser_session, *ERROR_BANNER_LOCATOR, "PasswordErrorBanner", timeout=8.0)

    def is_showing(self, timeout: float = 3.0) -> bool:
        return self._field.exists(timeout=timeout)

    def submit(self, password: str, attempts: int = 3, advance_timeout: float = 15.0) -> bool:
        """Same verify+retry treatment as EmailStep.submit() -- see its docstring."""
        for attempt in range(attempts):
            self._field.type_text(password)
            self._signin_button.click()
            if self._field.wait_until_gone(timeout=advance_timeout):
                return True
        return False

    def submit_and_expect_error(self, wrong_password: str, timeout: float = 8.0) -> bool:
        """Negative-path check -- single attempt only. See EmailStep.submit_and_expect_error.
        This step's own confirmed error text explicitly warns the account locks after 6
        incorrect attempts -- all the more reason this must never retry.
        """
        self._field.type_text(wrong_password)
        self._signin_button.click()
        return self._error_banner.exists(timeout=timeout)


class OtpStep:
    def __init__(self, browser_session):
        self._boxes = [
            BaseComponent(browser_session, *otp_box_locator(name), f"OtpBox{name}")
            for name in OTP_BOX_NAMES
        ]
        self._verify_button = BaseComponent(browser_session, *OTP_VERIFY_BUTTON_LOCATOR, "OtpVerifyButton")
        self._error_banner = BaseComponent(browser_session, *ERROR_BANNER_LOCATOR, "OtpErrorBanner", timeout=8.0)

    def is_showing(self, timeout: float) -> bool:
        return self._boxes[0].exists(timeout=timeout)

    def submit(self, otp: str) -> None:
        for digit, box in zip(otp, self._boxes):
            box.type_text(digit)
        self._verify_button.click()

    def submit_and_expect_error(self, wrong_otp: str, timeout: float = 8.0) -> bool:
        """Negative-path check -- single attempt only, same reasoning as
        PasswordStep.submit_and_expect_error (this step's error text carries the same
        6-attempt account-lockout warning).
        """
        for digit, box in zip(wrong_otp, self._boxes):
            box.type_text(digit)
        self._verify_button.click()
        return self._error_banner.exists(timeout=timeout)
