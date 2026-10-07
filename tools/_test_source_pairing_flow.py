"""
Live test of SourcePairingFlow: launches the Source app, drives it to the pairing-code
screen, and continuously publishes the current code to the Coordination Service.

Confirmed requirement: portable, no hardcoded paths/credentials. Set these before
running:
    DDA_SOURCE_BUILD_PATH   (path to the ALREADY-INSTALLED DellDataAssistant.exe --
                             NOT the original downloaded installer; see
                             factory/config.py's SOURCE_EXE_NAME docstring)
    DDA_COORDINATION_SERVICE_URL   (optional; defaults to http://127.0.0.1:8000)
    DDA_RUN_ID                     (optional; defaults to "manual-test-run")
"""

import os
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from prerequisites import ensure_target_prerequisites
from factory.session import MachineRole, Session
from factory.coordination_client import CoordinationClient
from flows.source.pairing_flow import SourcePairingFlow


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(
            f"Missing required environment variable {name} -- see this file's module "
            "docstring. Set it (e.g. in .env) and re-run."
        )
    return value


build_path = _require_env("DDA_SOURCE_BUILD_PATH")
run_id = os.environ.get("DDA_RUN_ID", "manual-test-run")

ensure_target_prerequisites()  # same generic checks (dev mode, WinAppDriver) regardless of role

t0 = time.monotonic()
session = Session.get(MachineRole.SOURCE, build_path=build_path)
print(f"[{time.monotonic()-t0:.1f}s] Attached. session_id={session.app.session_id}")

coordination_client = CoordinationClient()
flow = SourcePairingFlow(session.app, run_id=run_id, coordination_client=coordination_client)

try:
    flow.run()
    print(f"[{time.monotonic()-t0:.1f}s] SUCCESS: pairing completed.")
except BaseException:
    flow.log.error("Source pairing test failed -- cleaning up")
    session.close()
    raise
