"""
Target PC app-side dialog/modal elements that can appear on top of other screens during
the sign-in sequence (Target-only: Source PC has no authentication step). See
PROJECT_PLAN.md Sec 5.3/5.4 and tools/phase0_inspection_notes.md for how each was
confirmed.
"""

import time
from typing import Optional

from components.base_component import BaseComponent
from locators.target.close_apps_dialog import CLOSE_APPLICATION_BUTTON_LOCATOR, CLOSE_APPS_HEADING_LOCATOR
from locators.target.migration_preparation_transition import TRANSITION_PHRASES
from locators.target.sign_in_failed_dialog import SIGN_IN_FAILED_HEADING_LOCATOR, SIGN_IN_FAILED_RETRY_BUTTON_LOCATOR
from locators.target.sign_in_waiting_modal import SIGN_IN_WAITING_HEADING_LOCATOR, SIGN_IN_WAITING_CANCEL_BUTTON_LOCATOR
from locators.target.trust_network_dialog import TRUST_NETWORK_BUTTON_LOCATOR


class TrustNetworkDialog:
    """"Connect to a trusted network" dialog, confirmed appearing after sign-in."""

    def __init__(self, app_session):
        self._button = BaseComponent(app_session, *TRUST_NETWORK_BUTTON_LOCATOR, "TrustNetworkButton")

    def is_showing(self, timeout: float = 2.0) -> bool:
        return self._button.exists(timeout=timeout)

    def accept(self, timeout: float = 2.0) -> bool:
        """Clicks "Trust Network" if the dialog is showing. Returns whether it was
        present at all, so callers can distinguish "already past this dialog" from
        "accepted it just now" without a separate is_showing() call.
        """
        if not self._button.exists(timeout=timeout):
            return False
        self._button.click()
        return True


class SignInFailedDialog:
    """"There was a problem signing in" / "Sign-in failed. Please try again." -- shown
    layered over the Welcome screen when authentication fails or is cancelled. Confirmed
    from a user-supplied flow diagram ("dell screens flow.pdf", 2026-10-05): has a Cancel
    and a Retry button.

    Critically, the user confirmed directly that MigrationPreparationTransition's own
    transition screen (below) can appear even when sign-in was actually cancelled -- so
    that screen's appearance ALONE is not a reliable success signal. This dialog is the
    other half of the race: whichever of the two appears first after OTP submission is
    what actually tells success and failure apart (see SignInFlow._wait_for_auth_outcome).
    """

    def __init__(self, app_session):
        self._heading = BaseComponent(app_session, *SIGN_IN_FAILED_HEADING_LOCATOR, "SignInFailedHeading")
        self._retry_button = BaseComponent(
            app_session, *SIGN_IN_FAILED_RETRY_BUTTON_LOCATOR, "SignInFailedRetryButton"
        )

    def is_showing(self, timeout: float = 0.1) -> bool:
        return self._heading.exists(timeout=timeout)

    def retry(self, timeout: float = 2.0) -> bool:
        """Clicks Retry if the dialog is showing. Returns whether it was present at all
        (same pattern as TrustNetworkDialog.accept()).
        """
        if not self._heading.exists(timeout=timeout):
            return False
        self._retry_button.click()
        return True


class SignInWaitingModal:
    """"Sign in to MyDell to continue" -- shown in the app (not the browser) while the
    external browser-based sign-in is in progress: "We've opened your web browser so you
    can sign in and continue...", a "Having trouble? Retry" link, a "Waiting for
    sign-in..." status, and a Cancel button. Confirmed to exist from the project's
    original reference walkthrough; this is the deliberate, user-confirmed way to force a
    real sign-in cancellation for testing the cancel-and-retry path (see
    tools/_test_cancel_and_retry_live.py) -- NOT something a flow clicks as part of normal
    operation (see tools/signin_flow_test_plan.md's exclusion list).

    The Cancel button's exact accessible name is unconfirmed live -- see
    locators/target/sign_in_waiting_modal.py.
    """

    def __init__(self, app_session):
        self._heading = BaseComponent(app_session, *SIGN_IN_WAITING_HEADING_LOCATOR, "SignInWaitingHeading")
        self._cancel_button = BaseComponent(
            app_session, *SIGN_IN_WAITING_CANCEL_BUTTON_LOCATOR, "SignInWaitingCancelButton"
        )

    def is_showing(self, timeout: float = 2.0) -> bool:
        return self._heading.exists(timeout=timeout)

    def cancel(self, timeout: float = 2.0) -> bool:
        """Clicks Cancel if the modal is showing. Returns whether it was present at all
        (same pattern as TrustNetworkDialog.accept()).
        """
        if not self._heading.exists(timeout=timeout):
            return False
        self._cancel_button.click()
        return True


class CloseAppsDialog:
    """"We need to close all other applications" -- shown when the app detects other
    running applications (e.g. Control Panel, a browser) blocking migration. Confirmed
    from a user-supplied screenshot (2026-10-06). Can appear unpredictably during a long
    wait (same as ConfirmAccountsDialog), not tied to one specific prior step.
    """

    def __init__(self, app_session):
        self._heading = BaseComponent(app_session, *CLOSE_APPS_HEADING_LOCATOR, "CloseAppsHeading")
        self._close_application_button = BaseComponent(
            app_session, *CLOSE_APPLICATION_BUTTON_LOCATOR, "CloseApplicationButton"
        )

    def is_showing(self, timeout: float = 2.0) -> bool:
        return self._heading.exists(timeout=timeout)

    def accept(self, timeout: float = 2.0) -> bool:
        """Clicks "Close Application" if the dialog is showing. Returns whether it was
        present at all (same pattern as TrustNetworkDialog.accept()).
        """
        if not self._heading.exists(timeout=timeout):
            return False
        self._close_application_button.click()
        return True


class MigrationPreparationTransition:
    """Confirmed via user-supplied screenshots (2026-10-05): between OTP submission (or
    the "Welcome back" screen's Get Started button) and the trust-network dialog, the app
    passes through one or more transitional screens that span the manual Windows UAC
    approval (UAC runs on the secure desktop, categorically invisible to UI Automation --
    there's no API-level way to see or click it). Confirmed order: "Test, <name>, we're
    getting things ready" / "We're checking your PC to make sure your files and settings
    are ready for the move" first, then "Starting the migration assistant -- this only
    takes a moment" second.

    Not every run necessarily shows both, and exact timing relative to UAC can vary, so
    rather than requiring one exact screen, this polls the raw page source (one /source
    call per iteration, not a per-candidate locator lookup) for ANY of the known
    transition phrases -- the concrete, pollable signal that UAC was approved and
    something moved forward, instead of blindly waiting on one specific screen with no
    visibility into progress.
    """

    def __init__(self, app_session):
        self._session = app_session

    def wait_until_any_showing(self, timeout: float, poll_interval: float = 1.0) -> Optional[str]:
        """Returns the matched phrase once any of them appears within timeout, or None
        if the timeout expires first.
        """
        deadline = time.monotonic() + timeout
        while True:
            try:
                source = self._session.page_source.lower()
            except Exception:
                source = ""
            for text in TRANSITION_PHRASES:
                if text in source:
                    return text
            if time.monotonic() >= deadline:
                return None
            time.sleep(poll_interval)
