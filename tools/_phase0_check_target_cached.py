"""
Checks whether the Target app can reach an already-signed-in shortcut WITHOUT touching
credentials at all -- zero risk to the (currently locked) test account. Launches the app,
checks only the pure passthrough/already-signed-in conditions, and stops immediately
without clicking Sign In if none of them are showing.
"""
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.prerequisites import ensure_target_prerequisites
from factory.session import MachineRole, Session
from components.target.sign_in_screen import WelcomeScreen, WelcomeBackScreen
from components.target.common_dialogs import TrustNetworkDialog
from components.target.pairing_discovery_screen import PairingDiscoveryScreen

ensure_target_prerequisites()

build_path = None
import os
build_path = os.environ.get("DDA_TARGET_BUILD_PATH")
if not build_path:
    raise SystemExit("DDA_TARGET_BUILD_PATH not set")

session = Session.get(MachineRole.TARGET, build_path=build_path)
print(f"Attached. session_id={session.app.session_id}")

pairing_discovery = PairingDiscoveryScreen(session.app)
trust_network = TrustNetworkDialog(session.app)
welcome_back = WelcomeBackScreen(session.app)
welcome = WelcomeScreen(session.app)

time.sleep(2)

if pairing_discovery.is_showing(timeout=3.0):
    print("ALREADY on pairing-discovery screen -- no action needed, zero credential risk.")
elif trust_network.is_showing(timeout=1.0):
    print("Trust-network dialog showing -- accepting (no credentials involved).")
    trust_network.accept()
elif welcome_back.is_showing(timeout=1.0):
    print("'Welcome back' screen showing -- clicking Get Started (no credentials involved).")
    welcome_back.click_get_started()
    print("Clicked. Waiting up to 60s for pairing-discovery or trust-network to appear...")
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        if pairing_discovery.is_showing(timeout=0.5):
            print("Reached pairing-discovery screen.")
            break
        if trust_network.is_showing(timeout=0.5):
            print("Trust-network dialog appeared -- accepting.")
            trust_network.accept()
        time.sleep(1)
    else:
        print("Did not reach pairing-discovery within 60s.")
elif welcome.is_showing(timeout=1.0):
    print("Plain Welcome screen (no cached session) -- STOPPING HERE, will not click "
          "Sign In since that would require credentials against the locked account.")
else:
    print("Unrecognized screen -- stopping without touching anything.")

print("Done. Leaving app running for inspection -- not closing session.")
