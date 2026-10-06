"""
Pytest fixtures for Session-managed test runs. See factory/session.py's own docstring for
the Session lifecycle this wraps (app + browser + WinAppDriver, all torn down together).

Function-scoped (confirmed directly by the user, 2026-10-06): each test gets its own
fresh Session via Session.get()'s existing idempotent reuse-if-alive logic, and on ANY
failure in that test, everything closes together before the next test starts -- "it's
basically a session: if a single step fails then everything must be closed." A
session-scoped fixture was considered and rejected: state can leak between tests (e.g.
one test's already-signed-in shortcut masking what the next test actually needs to
exercise), and a mid-run failure's all-or-nothing teardown would force a relaunch before
the next test anyway, so sharing one launch across tests wouldn't actually save the cost
it looks like it would.

Credentials are environment-variable only, never hardcoded here or passed as pytest CLI
args (see PROJECT_PLAN.md Sec 4.7/7):
    DDA_TARGET_BUILD_PATH
    DDA_TARGET_SIGNIN_USERNAME
    DDA_TARGET_SIGNIN_PASSWORD
    DDA_TARGET_OTP_STATIC_VALUE
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from factory.session import MachineRole, Session


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        pytest.skip(f"{name} not set -- see tests/conftest.py's module docstring")
    return value


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    # Standard pytest recipe for exposing a test's pass/fail outcome to its own fixtures'
    # teardown code (fixtures only see the test function itself, not pytest's report) --
    # stashes the outcome of each phase (setup/call/teardown) on the test item so the
    # `session` fixture below can check rep_call.failed after yield.
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


@pytest.fixture
def session(request):
    """Yields a Session attached to the Target PC app. On teardown, closes everything
    (browser, app process, WinAppDriver) if -- and only if -- the test failed; a passing
    test's own flow logic is responsible for its own cleanup along the way (e.g.
    SignInFlow's _cleanup_after_failure calls session.close() itself on an internal
    exception). This fixture is the safety net for failures the flow didn't already
    handle (e.g. an assertion in the test itself, after flow.run() succeeded).
    """
    build_path = _require_env("DDA_TARGET_BUILD_PATH")
    sess = Session.get(MachineRole.TARGET, build_path=build_path)
    yield sess
    failed = getattr(request.node, "rep_call", None) is not None and request.node.rep_call.failed
    if failed:
        sess.close()


@pytest.fixture
def credentials():
    return {
        "username": _require_env("DDA_TARGET_SIGNIN_USERNAME"),
        "password": _require_env("DDA_TARGET_SIGNIN_PASSWORD"),
        "otp": _require_env("DDA_TARGET_OTP_STATIC_VALUE"),
    }
