"""
Adhoc, deliberately-invoked negative-path validation for the Target PC sign-in flow --
confirms the app's error banner appears correctly for a wrong email, wrong password, and
wrong OTP, each followed by the correct value, then completes the sign-in normally.

Moved OUT of SignInFlow's default run() path (2026-10-06): running this on every single
routine test run accumulated enough incorrect password/OTP attempts across repeated runs
to trip the test account's real 6-attempt lockout (both error banners explicitly warn of
this). Run this script ONLY when you specifically want to re-verify the error-message
wording/locators are still correct -- not as part of normal/routine testing. The default
flow (tools/_test_full_signin.py -> SignInFlow.run()) submits correct email/password
directly; it still exercises the cancel-and-retry mechanism via OTP's own deliberate
wrong-value-then-cancel, since that's not purely a negative-path check (see
flows/target/authentication/sign_in_flow.py's module docstring).

Sequence: wrong email -> confirm error banner -> correct email -> Continue
          wrong password -> confirm error banner -> correct password -> Sign In
          wrong OTP -> confirm error banner -> correct OTP -> Verify
          (completes the sign-in normally afterward, same as a routine run, so this
          doesn't leave the app/account in a half-finished state)

Env vars (same convention as tools/run_sign_in_flow.py):
    DDA_TARGET_BUILD_PATH
    DDA_TARGET_SIGNIN_USERNAME
    DDA_TARGET_SIGNIN_PASSWORD
    DDA_TARGET_OTP_STATIC_VALUE
"""

import os
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from prerequisites import ensure_target_prerequisites
from factory.session import MachineRole, Session
from flows.target.authentication.sign_in_flow import SignInFlow
from components.target.browser_sign_in_page import RestorePagesDialog, EmailStep, PasswordStep, OtpStep


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(
            f"Missing required environment variable {name} -- see this file's module "
            "docstring. Set it (e.g. in .env) and re-run."
        )
    return value


build_path = _require_env("DDA_TARGET_BUILD_PATH")
username = _require_env("DDA_TARGET_SIGNIN_USERNAME")
password = _require_env("DDA_TARGET_SIGNIN_PASSWORD")
otp = _require_env("DDA_TARGET_OTP_STATIC_VALUE")

ensure_target_prerequisites()

t0 = time.monotonic()


def log(msg: str) -> None:
    print(f"[{time.monotonic() - t0:.1f}s] {msg}")


session = Session.get(MachineRole.TARGET, build_path=build_path)
log(f"Attached. session_id={session.app.session_id}")

flow = SignInFlow(session, username=username, password=password, otp=otp)
deadline = time.monotonic() + 300.0

try:
    if flow._already_signed_in():
        log("App is already signed in -- this adhoc test needs a FRESH sign-in to "
            "reach the email/password/OTP steps. Sign out in the app first, then rerun.")
        sys.exit(1)

    known_hwnds = session.snapshot_browser_windows()
    opened_browser = flow._click_sign_in_with_retry(known_hwnds)
    if not opened_browser:
        log("Sign-in click didn't open a browser (already-authenticated session "
            "detected) -- this test needs the full browser-based flow. Sign out and rerun.")
        sys.exit(1)

    log("Browser opened. Running negative-path checks for email, password, and OTP...")

    browser_session = session.attach_browser(known_hwnds, timeout=20.0)
    try:
        restore_pages_dialog = RestorePagesDialog(browser_session)
        restore_pages_dialog.dismiss_if_present()

        email_step = EmailStep(browser_session)
        if email_step.is_showing(timeout=20.0):
            wrong_username = username + "wrongtest"
            log("Email: submitting a deliberately wrong value...")
            if email_step.submit_and_expect_error(wrong_username):
                log("Email: error banner confirmed.")
            else:
                log("WARNING: Email error banner did not appear.")
            log("Email: submitting the correct value...")
            if not email_step.submit(username):
                raise RuntimeError("Email step did not advance after the correct value")
        else:
            log("Email step not present -- browser profile already has a session, skipping.")

        restore_pages_dialog.dismiss_if_present()
        password_step = PasswordStep(browser_session)
        if password_step.is_showing(timeout=20.0):
            wrong_password = password + "Wrong1!"
            log("Password: submitting a deliberately wrong value...")
            if password_step.submit_and_expect_error(wrong_password):
                log("Password: error banner confirmed.")
            else:
                log("WARNING: Password error banner did not appear.")
            log("Password: submitting the correct value...")
            if not password_step.submit(password):
                raise RuntimeError("Password step did not advance after the correct value")
        else:
            log("Password step not present -- already authenticated in this browser profile, skipping.")

        otp_step = OtpStep(browser_session)
        if otp_step.is_showing(timeout=20.0):
            restore_pages_dialog.dismiss_if_present()
            time.sleep(1.0)
            wrong_otp = "".join(str((int(d) + 1) % 10) for d in otp)
            log("OTP: submitting a deliberately wrong code...")
            if otp_step.submit_and_expect_error(wrong_otp):
                log("OTP: error banner confirmed.")
            else:
                log("WARNING: OTP error banner did not appear.")
            log("OTP: submitting the correct code...")
            otp_step.submit(otp)
        else:
            log("OTP step not present -- skipping.")

        log("Keeping the sign-in browser open while waiting for UAC and the real "
            "post-auth outcome...")
        flow._wait_for_uac_prompt_resolution(remaining=deadline - time.monotonic())
        outcome = flow._wait_for_auth_outcome(remaining=deadline - time.monotonic())
    finally:
        session.close_browser()
    log(f"Closed the sign-in browser window. Outcome: {outcome!r}")

    if outcome != "success":
        log("Did not reach success after the negative-path checks -- stopping.")
        sys.exit(1)

    flow._wait_for_trust_network_then_pairing_discovery(remaining=deadline - time.monotonic())
    log("SUCCESS: all three negative-path checks completed, reached pairing-discovery screen.")

except BaseException:
    # Same "any exception closes the driver and the app immediately" requirement as
    # SignInFlow.run() itself -- this script drives SignInFlow's internals directly
    # rather than through run(), so it needs the same safety net explicitly.
    flow.log.error("Adhoc negative-path test failed -- cleaning up")
    flow._cleanup_after_failure()
    raise
