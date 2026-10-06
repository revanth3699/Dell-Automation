"""
Live test of the cancel-and-retry path. Sequence confirmed directly by the user
(2026-10-06): wrong OTP -> deliberately click the OTP page's OWN Cancel button (below
Verify, in the browser) -> this STILL triggers a Windows UAC prompt (a human must
approve it -- automation cannot see or interact with it, same secure-desktop constraint
as the normal success path) -> once approved, the app shows "There was a problem signing
in" with its own Retry button -> click Retry -> whole browser-based sequence runs again,
submitting CORRECT values straight away this time (no repeated wrong-value checks) ->
rest of the flow (trust-network, pairing-discovery, wait-for-source) proceeds normally.

NOTE: this exact sequence is now SignInFlow.run()'s own default behavior every run (see
_handle_otp_step's run_negative_check parameter and _run_fresh_auth_with_retry's
attempt-0 gating in flows/target/authentication/sign_in_flow.py) -- there is no longer a
separate "cancel path" distinct from "retry on failure". This script is now mostly
redundant with just running tools/_test_full_signin.py; kept as a more verbose, isolated
diagnostic for this mechanism specifically, not because run() needs a separate test for it.

Reuses SignInFlow's real sub-components/methods directly (not a reimplementation) --
only the deliberate cancel point is hand-orchestrated here, since that's a test-only
maneuver that has no place in SignInFlow.run()'s normal production path (see
tools/signin_flow_test_plan.md's exclusion list: clicking Cancel is a real destructive
user choice, deliberately never automated as part of normal operation).

Confirms (or refutes) two previously-unconfirmed assumptions in one run:
1. The OtpStep.cancel() locator (locators/target/otp_step.py) is correct.
2. Cancelling there actually produces the SignInFailedDialog, as assumed by
   SignInFlow._wait_for_auth_outcome()'s whole design.

Confirmed requirement: this must work consistently across machines, not just the one it
was first written on -- build path and credentials are environment-variable only (same
convention as tools/run_sign_in_flow.py), never hardcoded. Set these before running:
    DDA_TARGET_BUILD_PATH         (path to DellDataAssistant.TargetPc.exe)
    DDA_TARGET_SIGNIN_USERNAME
    DDA_TARGET_SIGNIN_PASSWORD
    DDA_TARGET_OTP_STATIC_VALUE
"""

import os
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factory.driver_factory import DriverFactory, MachineRole
from factory.prerequisites import ensure_target_prerequisites
from factory.browser_driver_factory import browser_driver, list_browser_window_hwnds
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


driver = DriverFactory.get_app_driver(MachineRole.TARGET, build_path=build_path)
log(f"Attached. session_id={driver.session_id}")

flow = SignInFlow(driver, username=username, password=password, otp=otp)
deadline = time.monotonic() + 300.0

try:
    if flow._already_signed_in():
        log("App is already signed in -- this test needs a FRESH sign-in to reach the "
            "OTP step. Sign out in the app first, then rerun.")
        sys.exit(1)

    known_hwnds = list_browser_window_hwnds()
    opened_browser = flow._click_sign_in_with_retry(known_hwnds)
    if not opened_browser:
        log("Sign-in click didn't open a browser (already-authenticated session "
            "detected) -- this test needs the full browser-based flow. Sign out and rerun.")
        sys.exit(1)

    log("Browser opened. Driving to the OTP step for the deliberate-cancel pass...")

    with browser_driver(known_hwnds, timeout=20.0) as browser_session:
        restore_pages_dialog = RestorePagesDialog(browser_session)
        restore_pages_dialog.dismiss_if_present()

        flow._handle_email_step_if_present(browser_session, 20.0)
        flow._handle_password_step_if_present(browser_session, restore_pages_dialog, 20.0)

        otp_step = OtpStep(browser_session)
        if not otp_step.is_showing(timeout=20.0):
            log("OTP step never appeared -- aborting test (unexpected state).")
            sys.exit(1)

        restore_pages_dialog.dismiss_if_present()
        time.sleep(1.0)

        wrong_otp = "".join(str((int(d) + 1) % 10) for d in flow.otp)
        log("Submitting deliberately wrong OTP...")
        if otp_step.submit_and_expect_error(wrong_otp):
            log("Wrong-OTP error banner confirmed.")
        else:
            log("WARNING: expected error banner did not appear after wrong OTP.")

        log("Deliberately clicking the OTP page's own Cancel button instead of "
            "entering the correct OTP...")
        if not otp_step.cancel():
            log("OTP Cancel button not found/clicked -- cannot proceed "
                "(locator may be wrong; see locators/target/otp_step.py).")
            sys.exit(1)
        log("Clicked Cancel on the OTP page.")

    log("Browser window closed (via our own cleanup on exiting the with-block). "
        "Confirmed directly by the user (2026-10-06): cancelling here still triggers a "
        "Windows UAC prompt -- automation cannot see or interact with it (secure "
        "desktop). Please approve it manually if it appears; waiting for the app's "
        "'There was a problem signing in' dialog with real patience...")
    outcome = flow._wait_for_auth_outcome(remaining=deadline - time.monotonic())
    log(f"Outcome after cancel: {outcome!r}")

    if outcome != "failed":
        log("Did not detect the sign-in-failed dialog after cancelling -- the cancel "
            "mechanism or the dialog locator may not be what we assumed. Stopping here.")
        sys.exit(1)

    log("Clicking Retry on the sign-in-failed dialog...")
    known_hwnds = list_browser_window_hwnds()
    if not flow.sign_in_failed_dialog.retry():
        log("Retry button not found/clicked -- aborting.")
        sys.exit(1)

    if not flow._wait_for_new_browser(known_hwnds, timeout=30.0):
        log("Clicking Retry never opened a new browser window -- aborting.")
        sys.exit(1)
    log("New browser window opened after Retry.")

    # Confirmed directly by the user (2026-10-06): on this retry pass, submit correct
    # values straight away -- don't repeat the wrong-value negative checks. They were
    # already proven once on the first pass, and password/OTP both carry a confirmed
    # 6-attempt account lockout; there's no reason to burn more of that budget redoing
    # a check this run isn't about.
    with browser_driver(known_hwnds, timeout=20.0) as browser_session:
        restore_pages_dialog = RestorePagesDialog(browser_session)
        restore_pages_dialog.dismiss_if_present()

        email_step = EmailStep(browser_session)
        if email_step.is_showing(timeout=20.0):
            log("Submitting the correct email...")
            email_step.submit(username)
        else:
            log("Email step not present on retry -- continuing (may have been skipped).")

        restore_pages_dialog.dismiss_if_present()
        password_step = PasswordStep(browser_session)
        if password_step.is_showing(timeout=20.0):
            log("Submitting the correct password...")
            password_step.submit(password)
        else:
            log("Password step not present on retry -- continuing (may have been skipped).")

        otp_step = OtpStep(browser_session)
        if otp_step.is_showing(timeout=20.0):
            restore_pages_dialog.dismiss_if_present()
            time.sleep(1.0)
            log("Submitting the CORRECT OTP this time...")
            otp_step.submit(flow.otp)
        else:
            log("OTP step not present on retry -- continuing (may have been skipped).")

    log("OTP submitted (correct value). Waiting for the real post-auth outcome...")
    outcome2 = flow._wait_for_auth_outcome(remaining=deadline - time.monotonic())
    log(f"Outcome after correct OTP: {outcome2!r}")

    if outcome2 != "success":
        log("Did not reach success after the correct OTP on retry -- stopping.")
        sys.exit(1)

    flow._wait_for_trust_network_and_accept(remaining=deadline - time.monotonic())
    flow._confirm_reached_pairing_discovery(remaining=deadline - time.monotonic())
    log("SUCCESS: cancel-and-retry flow completed end-to-end, reached pairing-discovery screen.")

    found = flow.wait_for_source_pc()
    log(f"Source PC found: {found}")

except BaseException:
    # Same "any exception closes the driver and the app immediately" requirement as
    # SignInFlow.run() itself -- this script drives SignInFlow's internals directly
    # rather than through run(), so it needs the same safety net explicitly.
    flow.log.error("Cancel-and-retry test failed -- cleaning up")
    flow._cleanup_after_failure()
    raise
