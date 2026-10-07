import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.prerequisites import ensure_target_prerequisites
from factory.session import MachineRole, Session
from flows.target.authentication.sign_in_flow import SignInFlow
from locators.target.email_step import EMAIL_FIELD_LOCATOR
from components.base_component import BaseComponent


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(
            f"Missing required environment variable {name} -- same convention as "
            "tools/_test_full_signin.py. Set it (e.g. in .env) and re-run."
        )
    return value


build_path = _require_env("DDA_TARGET_BUILD_PATH")
username = _require_env("DDA_TARGET_SIGNIN_USERNAME")
password = _require_env("DDA_TARGET_SIGNIN_PASSWORD")
otp = _require_env("DDA_TARGET_OTP_STATIC_VALUE")

ensure_target_prerequisites()

session = Session.get(MachineRole.TARGET, build_path=build_path)
print("Attached to app. session_id=", session.app.session_id)

flow = SignInFlow(session, username=username, password=password, otp=otp)
known_hwnds = session.snapshot_browser_windows()
flow._click_sign_in_with_retry(known_hwnds)
print("Clicked sign-in.")

browser = session.attach_browser(known_hwnds, timeout=15.0)
print("Attached to browser.")

field = BaseComponent(browser, *EMAIL_FIELD_LOCATOR, "EmailField", timeout=10.0)
if not field.exists(timeout=5.0):
    print("Email field not present -- browser already has a session.")
    sys.exit(0)

print("Typing with verify+retry...")
field.type_text(username)
print("type_text returned without error -- verification passed internally.")

actual = field.get_text()
print("Double-checking from outside: field text =", repr(actual))
