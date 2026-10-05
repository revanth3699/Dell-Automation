import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factory.driver_factory import DriverFactory, MachineRole
from factory.prerequisites import ensure_target_prerequisites
from flows.target.authentication.sign_in_flow import SignInFlow
from factory.browser_driver_factory import attach_to_sign_in_browser
from components.target.browser_sign_in_page import EMAIL_FIELD_LOCATOR
from components.base_component import BaseComponent

ensure_target_prerequisites()

driver = DriverFactory.get_app_driver(
    MachineRole.TARGET,
    build_path=r"C:\Users\revan\Downloads\027df3321\Release\DellDataAssistant.TargetPc.exe",
)
print("Attached to app. session_id=", driver.session_id)

flow = SignInFlow(driver, username="sospigorda@necub.com", password="Dell@123", otp="123456")
flow._click_sign_in_with_retry()
print("Clicked sign-in.")

browser = attach_to_sign_in_browser(timeout=15.0)
print("Attached to browser.")

field = BaseComponent(browser, *EMAIL_FIELD_LOCATOR, "EmailField", timeout=10.0)
if not field.exists(timeout=5.0):
    print("Email field not present -- browser already has a session.")
    sys.exit(0)

print("Typing with verify+retry...")
field.type_text("sospigorda@necub.com")
print("type_text returned without error -- verification passed internally.")

actual = field.get_text()
print("Double-checking from outside: field text =", repr(actual))
