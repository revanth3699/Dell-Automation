import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factory.driver_factory import DriverFactory, MachineRole
from factory.prerequisites import ensure_target_prerequisites
from flows.target.authentication.sign_in_flow import SignInFlow

ensure_target_prerequisites()

t0 = time.monotonic()
driver = DriverFactory.get_app_driver(
    MachineRole.TARGET,
    build_path=r"C:\Users\revan\Downloads\027df3321\Release\DellDataAssistant.TargetPc.exe",
)
print(f"[{time.monotonic()-t0:.1f}s] Attached. session_id={driver.session_id}")

flow = SignInFlow(driver, username="sospigorda@necub.com", password="Dell@123", otp="123456")
flow.run()
print(f"[{time.monotonic()-t0:.1f}s] SUCCESS: sign-in flow completed, reached pairing-discovery screen.")

found = flow.wait_for_source_pc()
print(f"[{time.monotonic()-t0:.1f}s] Source PC found: {found}")
