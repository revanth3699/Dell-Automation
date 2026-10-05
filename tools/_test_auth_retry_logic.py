"""
Mock-based verification of SignInFlow._run_fresh_auth_with_retry()'s control flow --
the cancel-and-retry logic -- with no real app/browser/WinAppDriver involved. Verifies
two scenarios deterministically and repeatably:

1. Sign-in fails once, then succeeds on retry -> returns normally, Retry clicked once.
2. Sign-in fails on every attempt -> raises SignInError after exactly MAX_AUTH_RETRIES
   attempts, having clicked Retry that many times.

Does NOT prove the real "There was a problem signing in" dialog locator is correct --
that needs a live run where a human triggers a real cancellation (see
tools/signin_flow_test_plan.md). This only proves the Python control flow around it is
correct: race the two outcomes, click Retry and redo the whole sequence on failure, give
up after the cap.
"""

import sys
import time
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from flows.target.authentication.sign_in_flow import SignInFlow, SignInError


class FakeBrowserSession:
    """find_element always raises -- makes every BaseComponent.exists() check (used by
    RestorePagesDialog/EmailStep/PasswordStep/OtpStep's is_showing()) correctly resolve
    to False, so each step logs 'not present, skipping' and the flow reaches the
    post-OTP race quickly.
    """

    def find_element(self, by, value):
        raise RuntimeError("no such element (fake session)")

    @property
    def page_source(self):
        return ""

    def get_screenshot_as_png(self):
        return b""

    def quit(self):
        pass


class OutcomeController:
    def __init__(self, outcomes):
        self.outcomes = outcomes  # e.g. ["failed", "success"]
        self.index = 0
        self.retry_calls = 0

    def current_outcome(self):
        return self.outcomes[min(self.index, len(self.outcomes) - 1)]


class FakeSignInFailedDialog:
    def __init__(self, controller):
        self.controller = controller

    def is_showing(self, timeout: float = 0.1) -> bool:
        return self.controller.current_outcome() == "failed"

    def retry(self, timeout: float = 2.0) -> bool:
        self.controller.retry_calls += 1
        self.controller.index += 1
        return True


class FakeMigrationTransition:
    def __init__(self, controller):
        self.controller = controller

    def wait_until_any_showing(self, timeout: float, poll_interval: float = 1.0):
        if self.controller.current_outcome() == "success":
            return "we're getting things ready"
        return None


@contextmanager
def fake_browser_driver(known_hwnds, timeout=20.0):
    yield FakeBrowserSession()


def run_scenario(name: str, outcomes: list[str], expect_success: bool, expect_retry_calls: int) -> None:
    print(f"\n--- Scenario: {name} ---")
    controller = OutcomeController(outcomes)
    flow = SignInFlow(app_session=None, username="u", password="p", otp="123456")
    flow.sign_in_failed_dialog = FakeSignInFailedDialog(controller)
    flow.migration_preparation_transition = FakeMigrationTransition(controller)

    deadline = time.monotonic() + 60.0
    with patch("flows.target.authentication.sign_in_flow.browser_driver", fake_browser_driver), \
         patch("flows.target.authentication.sign_in_flow.list_browser_window_hwnds", lambda: set()), \
         patch("flows.target.authentication.sign_in_flow.find_new_browser_window_hwnd", lambda known: "FAKEHWND"):
        try:
            flow._run_fresh_auth_with_retry(known_hwnds=set(), step_timeout=5.0, deadline=deadline)
            succeeded = True
        except SignInError as exc:
            succeeded = False
            print(f"  raised SignInError (expected if not expect_success): {exc}")

    assert succeeded == expect_success, f"expected success={expect_success}, got success={succeeded}"
    assert controller.retry_calls == expect_retry_calls, (
        f"expected Retry() called {expect_retry_calls} time(s), got {controller.retry_calls}"
    )
    print(f"  Retry() called {controller.retry_calls} time(s) -- matches expected")
    print(f"  PASS")


run_scenario(
    "fails once, then succeeds", outcomes=["failed", "success"],
    expect_success=True, expect_retry_calls=1,
)
run_scenario(
    "fails on every attempt (hits MAX_AUTH_RETRIES)", outcomes=["failed", "failed", "failed"],
    expect_success=False, expect_retry_calls=SignInFlow.MAX_AUTH_RETRIES,
)

print("\nAll scenarios passed.")
