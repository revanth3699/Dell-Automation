"""Phase 2: validates SignInFlow end-to-end, using the pytest-managed Session fixture
(see conftest.py) for the app+browser+WinAppDriver lifecycle. Requires DDA_TARGET_BUILD_PATH
and the DDA_TARGET_SIGNIN_*/DDA_TARGET_OTP_STATIC_VALUE credentials to be set -- skipped
otherwise (see conftest.py's _require_env).
"""

from flows.target.authentication.sign_in_flow import SignInFlow


def test_sign_in_reaches_pairing_discovery(session, credentials):
    flow = SignInFlow(session, credentials["username"], credentials["password"], credentials["otp"])
    flow.run()
