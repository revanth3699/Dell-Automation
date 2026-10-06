"""
Live test: drives Target to the pairing-discovery screen using ONLY the cached/
already-signed-in shortcuts -- zero credential risk. Aborts loudly rather than typing
username/password/otp if a fresh sign-in would be required (the test account has a real
6-attempt lockout and has already been hit twice today -- see the
feedback_test_account_lockout memory note). Once at pairing-discovery, waits for Source
PC to be found, then fetches and enters the pairing code via the Coordination Service
(TargetPairingFlow.enter_pairing_code_from_coordination_service) -- run alongside
tools/_test_source_pairing_flow.py (same DDA_RUN_ID) in a separate shell for the real
two-sided test.

Env vars:
    DDA_TARGET_BUILD_PATH
    DDA_RUN_ID (optional; defaults to "manual-two-machine-test" -- must match the
                run_id tools/_test_source_pairing_flow.py is given)
"""

import os
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from components.target.common_dialogs import TrustNetworkDialog
from components.target.pairing_discovery_screen import PairingDiscoveryScreen
from components.target.sign_in_screen import WelcomeBackScreen, WelcomeScreen
from factory.config import TARGET_PROCESS_NAME
from factory.prerequisites import ensure_target_prerequisites
from factory.session import MachineRole, Session, _find_main_window_hwnd
from flows.target.pairing_flow import TargetPairingFlow


def assert_target_alive() -> None:
    if _find_main_window_hwnd(TARGET_PROCESS_NAME) is None:
        log("Target app window is gone -- it most likely crashed. Aborting.")
        sys.exit(1)

build_path = os.environ.get("DDA_TARGET_BUILD_PATH")
if not build_path:
    raise SystemExit("Missing DDA_TARGET_BUILD_PATH")
run_id = os.environ.get("DDA_RUN_ID", "manual-two-machine-test")

t0 = time.monotonic()


def log(msg: str) -> None:
    print(f"[{time.monotonic() - t0:.1f}s] {msg}")


ensure_target_prerequisites()
session = Session.get(MachineRole.TARGET, build_path=build_path)
log(f"Attached. session_id={session.app.session_id}")

welcome = WelcomeScreen(session.app)
welcome_back = WelcomeBackScreen(session.app)
trust_network = TrustNetworkDialog(session.app)
pairing_discovery = PairingDiscoveryScreen(session.app)

time.sleep(2)

if pairing_discovery.is_showing(timeout=3.0):
    log("Already on pairing-discovery screen.")
elif trust_network.is_showing(timeout=1.0):
    log("Trust-network dialog showing -- accepting (no credentials involved).")
    trust_network.accept()
elif welcome_back.is_showing(timeout=1.0):
    log("'Welcome back' screen -- clicking Get Started (cached session, zero credential risk).")
    welcome_back.click_get_started()
elif welcome.is_showing(timeout=1.0):
    log("FRESH Welcome screen (no cached session) -- ABORTING. Proceeding would require "
        "real credential entry against a possibly-still-locked account.")
    session.close()
    sys.exit(1)
else:
    log("Unrecognized screen -- aborting without touching anything.")
    session.close()
    sys.exit(1)

log("Waiting up to 60s for pairing-discovery / trust-network to resolve...")
deadline = time.monotonic() + 60
reached = False
while time.monotonic() < deadline:
    assert_target_alive()
    if pairing_discovery.is_showing(timeout=0.5):
        log("Reached pairing-discovery screen.")
        reached = True
        break
    if trust_network.is_showing(timeout=0.5):
        trust_network.accept()
    time.sleep(1)

if not reached:
    log("Did not reach pairing-discovery within 60s -- aborting.")
    sys.exit(1)

log(f"Waiting up to 600s for Source PC to be found (run_id={run_id!r})...")
found = pairing_discovery.wait_until_source_found(timeout=600.0)
log(f"Source PC found: {found}")
if not found:
    sys.exit(1)

log("Entering pairing code via Coordination Service fetch...")
TargetPairingFlow(session.app).enter_pairing_code_from_coordination_service(run_id, fetch_timeout=120.0)
log("PAIRING COMPLETE.")
