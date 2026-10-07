"""
Interactive Target PC sign-in (+ optional pairing) test runner: ensures prerequisites,
launches + attaches the app (same recipe as tools/launch_target_app.py), then drives the
full SignInFlow end to end -- including the negative-path wrong-credential checks on the
email/password/OTP steps -- and optionally TargetPairingFlow if a pairing code is given.

Credentials are environment-variable only, never CLI args (see PROJECT_PLAN.md Sec 4.7/7):
    DDA_TARGET_SIGNIN_USERNAME
    DDA_TARGET_SIGNIN_PASSWORD
    DDA_TARGET_OTP_STATIC_VALUE

Usage:
    python tools/run_sign_in_flow.py [--build-path PATH] [--pairing-code CODE]

With --with-mock-server, also starts the GlassFloor entitlement mock server first (see
PROJECT_PLAN.md Sec 5.3a) and launches the app with the matching CLI args:

    python tools/run_sign_in_flow.py --with-mock-server \
        [--build-path PATH] [--mock-server-package PATH] [--secret my-secret-active]

For automatic pairing against an independent Source-side run (see
flows/source/pairing_flow.py's SourcePairingFlow and tools/_test_source_pairing_flow.py),
pass --run-id matching whatever run_id Source is publishing to, instead of
--pairing-code -- the code is then fetched from the Coordination Service right before
entry, not supplied up front. If neither --pairing-code nor --run-id is given, this waits
(up to 10 min, matching the app's own PairingTimeoutInMilliseconds) for Source PC to be
found and then stops.

Deliberately NOT wrapped in a main()/def-and-call structure -- confirmed via live testing
(2026-10-05, reproduced independently by both the user and in-agent runs) that the
identical logic, run as flat top-level script code, works reliably every time, while the
same logic called from inside a function silently crashed (no traceback, no stderr, exit
code 255) immediately after the launch+attach call, consistently. This is the same
unresolved "mystery crash" class PROJECT_PLAN.md Sec 4.2/5.3b already documents (not fully
root-caused there either) -- not re-wrapped in a function here on purpose, pending a real
fix.
"""

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.mock_server import start_mock_server
from utils.prerequisites import ensure_mock_server_prerequisites, ensure_target_prerequisites
from factory.session import MachineRole, Session
from flows.target.authentication.sign_in_flow import SignInFlow
from flows.target.pairing_flow import TargetPairingFlow
from reports.action_reporter import ActionReporter
from reports.html_report_builder import build_report


def _prompt_for_path(label: str) -> str:
    while True:
        raw = input(f"{label}: ").strip().strip('"')
        path = Path(raw)
        if path.exists():
            return str(path)
        print(f"  Not found: {raw!r} -- try again.")


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(
            f"Missing required environment variable {name} -- credentials are env-var "
            "only (see PROJECT_PLAN.md Sec 4.7/7), never CLI args. Set it and re-run."
        )
    return value


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--build-path", help="Path to DellDataAssistant.TargetPc.exe (skips the prompt)")
parser.add_argument("--with-mock-server", action="store_true",
                     help="Start the GlassFloor mock server first and launch the app against it")
parser.add_argument("--mock-server-package", help="Path to the extracted GlassFloor-TestPackage folder")
parser.add_argument("--secret", default="my-secret-active",
                     help="Mock server scenario secret (default: my-secret-active)")
parser.add_argument("--port", type=int, default=8443, help="Mock server port (default: 8443)")
parser.add_argument("--pairing-code", help="If given, enters this literal pairing code after sign-in")
parser.add_argument("--run-id", help="If given (and --pairing-code isn't), fetches the current "
                     "pairing code from the Coordination Service for this run_id instead")
args = parser.parse_args()

_run_id = args.run_id or f"signin-{int(time.time())}"
ActionReporter.start_run(_run_id, "target")

username = _require_env("DDA_TARGET_SIGNIN_USERNAME")
password = _require_env("DDA_TARGET_SIGNIN_PASSWORD")
otp = _require_env("DDA_TARGET_OTP_STATIC_VALUE")

print("Checking Target PC prerequisites...")
ensure_target_prerequisites()

build_path = args.build_path or _prompt_for_path("Path to DellDataAssistant.TargetPc.exe")

app_arguments = None
if args.with_mock_server:
    print("Checking mock server prerequisites...")
    node_path = ensure_mock_server_prerequisites()
    package_path = args.mock_server_package or _prompt_for_path(
        "Path to the extracted GlassFloor-TestPackage folder"
    )
    print(f"Starting mock server on port {args.port} with secret {args.secret!r}...")
    mock_server = start_mock_server(package_path, args.secret, args.port, node_path=node_path)
    print(f"Mock server listening on {mock_server.server_address}")
    app_arguments = [mock_server.secret, mock_server.cert_path, mock_server.server_address]

print(f"Launching and attaching to: {build_path}")
session = Session.get(MachineRole.TARGET, build_path=build_path, app_arguments=app_arguments)
print(f"Attached. session_id={session.app.session_id}")

sign_in_flow = SignInFlow(session, username, password, otp)
sign_in_flow.run()
print("SignInFlow complete -- reached the pairing-discovery screen.")

if args.pairing_code:
    print("Entering pairing code...")
    TargetPairingFlow(session.app).enter_pairing_code(args.pairing_code)
    print("Pairing complete.")
elif args.run_id:
    print(f"Fetching pairing code from the Coordination Service for run_id={args.run_id!r}...")
    TargetPairingFlow(session.app).enter_pairing_code_from_coordination_service(args.run_id)
    print("Pairing complete.")
else:
    print("No --pairing-code/--run-id given -- waiting for Source PC to be found (up to 10 min)...")
    if sign_in_flow.wait_for_source_pc():
        print("Source PC found. Re-run with --pairing-code <code> or --run-id <id> to enter it automatically.")

report_path = build_report()
print(f"Report written to: {report_path}")
