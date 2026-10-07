"""
Quick non-interactive smoke test of the full sign-in flow. For anything beyond a quick
local check, prefer tools/run_sign_in_flow.py (the portable, CLI-driven entry point with
prompted/argument build path and optional pairing-code support).

Confirmed requirement: this must work consistently across machines, not just the one it
was first written on -- build path and credentials are environment-variable only (same
convention as tools/run_sign_in_flow.py), never hardcoded. Set these before running:
    DDA_TARGET_BUILD_PATH         (path to DellDataAssistant.TargetPc.exe)
    DDA_TARGET_SIGNIN_USERNAME
    DDA_TARGET_SIGNIN_PASSWORD
    DDA_TARGET_OTP_STATIC_VALUE
"""

import os
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.prerequisites import ensure_target_prerequisites
from factory.session import MachineRole, Session
from flows.target.authentication.sign_in_flow import SignInFlow


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(
            f"Missing required environment variable {name} -- see this file's module "
            "docstring. Set it (e.g. in .env) and re-run."
        )
    return value


build_path = _require_env("DDA_TARGET_BUILD_PATH")
username = _require_env("DDA_TARGET_SIGNIN_USERNAME")
password = _require_env("DDA_TARGET_SIGNIN_PASSWORD")
otp = _require_env("DDA_TARGET_OTP_STATIC_VALUE")

ensure_target_prerequisites()

t0 = time.monotonic()
session = Session.get(MachineRole.TARGET, build_path=build_path)
print(f"[{time.monotonic()-t0:.1f}s] Attached. session_id={session.app.session_id}")

flow = SignInFlow(session, username=username, password=password, otp=otp)
flow.run()
print(f"[{time.monotonic()-t0:.1f}s] SUCCESS: sign-in flow completed, reached pairing-discovery screen.")

found = flow.wait_for_source_pc()
print(f"[{time.monotonic()-t0:.1f}s] Source PC found: {found}")
