"""
RoleRunner: the real entry point for one independent automation process -- chains this
machine's own role (Target or Source) through its full flow sequence (sign-in/discovery
-> pairing), given just a role and a run_id shared between the two independent
processes/machines. See PROJECT_PLAN.md Sec 4.6.

`tools/*.py` scripts are dev/debug helpers only (manual, piecemeal testing of one flow
or component at a time, used throughout Phase 0-3 development) -- this is the one
command meant for actually running a role end to end in production, chaining its real
flows together rather than poking at internals.

Data-selection/transfer phases (Phase 4) are not implemented yet -- run() currently ends
once pairing is confirmed (Target) or Target has paired (Source). Extending to later
phases means adding more flow calls in each role's branch below, not a redesign.

Usage:
    python -m orchestration.role_runner --role target --run-id my-migration
    python -m orchestration.role_runner --role source --run-id my-migration

Both machines must be given the SAME run_id -- a plain correlation label (not a secret),
agreed on by whoever starts the two independent runs (see factory/coordination_client.py).

Env vars (role-specific, see each branch below):
    Target: DDA_TARGET_BUILD_PATH, DDA_TARGET_SIGNIN_USERNAME,
            DDA_TARGET_SIGNIN_PASSWORD, DDA_TARGET_OTP_STATIC_VALUE
    Source: DDA_SOURCE_BUILD_PATH
Both also read DDA_COORDINATION_SERVICE_URL (see factory/config.py; defaults to
http://127.0.0.1:8000 -- set it to the OTHER machine's address, or this machine's own if
it's the one hosting the Coordination Service, see utils/run_coordination_service.py).
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factory.coordination_client import CoordinationClient
from factory.prerequisites import ensure_target_prerequisites
from factory.session import MachineRole, Session
from flows.source.pairing_flow import SourcePairingFlow
from flows.source.transfer_flow import SourceTransferFlow
from flows.target.authentication.sign_in_flow import SignInFlow
from flows.target.pairing_flow import TargetPairingFlow
from flows.target.transfer_flow import TargetTransferFlow


class RoleRunnerError(Exception):
    pass


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RoleRunnerError(
            f"Missing required environment variable {name}. Set it (e.g. in .env) and re-run."
        )
    return value


class RoleRunner:
    @staticmethod
    def run(role: MachineRole, run_id: str) -> None:
        """Runs this machine's own role through to a paired state. Credentials/build
        paths come from environment variables only, never passed through here as
        arguments (see module docstring for which ones each role needs)."""
        ensure_target_prerequisites()  # same generic checks (dev mode, WinAppDriver) regardless of role

        if role is MachineRole.TARGET:
            RoleRunner._run_target(run_id)
        elif role is MachineRole.SOURCE:
            RoleRunner._run_source(run_id)
        else:
            raise RoleRunnerError(f"Unknown role: {role!r}")

    @staticmethod
    def _run_target(run_id: str) -> None:
        build_path = _require_env("DDA_TARGET_BUILD_PATH")
        username = _require_env("DDA_TARGET_SIGNIN_USERNAME")
        password = _require_env("DDA_TARGET_SIGNIN_PASSWORD")
        otp = _require_env("DDA_TARGET_OTP_STATIC_VALUE")

        session = Session.get(MachineRole.TARGET, build_path=build_path)
        try:
            # SignInFlow.run() already owns its own cleanup-on-failure internally (see
            # its own try/except BaseException) -- but a failure AFTER it returns
            # normally (in wait_for_source_pc() or pairing below) would not be caught
            # by that internal handler, so this method wraps the whole sequence too,
            # per the same "if a single step fails then everything must be closed"
            # requirement SignInFlow itself follows.
            sign_in_flow = SignInFlow(session, username, password, otp)
            sign_in_flow.run()

            if not sign_in_flow.wait_for_source_pc():
                raise RoleRunnerError("Source PC was not found within the pairing timeout")

            # Polling the Coordination Service only starts once the "Let's connect your
            # two PCs" code-entry screen is actually showing -- see
            # TargetPairingFlow.enter_pairing_code_from_coordination_service(), which
            # waits for that screen first and only then calls CoordinationClient.wait_for().
            TargetPairingFlow(session.app).enter_pairing_code_from_coordination_service(run_id)
            transfer_flow = TargetTransferFlow(session.app)
            transfer_flow.start_transfer()
            transfer_flow.wait_for_completion()
        except BaseException:
            session.close()
            raise

    @staticmethod
    def _run_source(run_id: str) -> None:
        build_path = _require_env("DDA_SOURCE_BUILD_PATH")

        session = Session.get(MachineRole.SOURCE, build_path=build_path)
        try:
            coordination_client = CoordinationClient()
            flow = SourcePairingFlow(session.app, run_id=run_id, coordination_client=coordination_client)
            flow.run()
            SourceTransferFlow(session.app).wait_for_transfer_to_start()
        except BaseException:
            session.close()
            raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", required=True, choices=["target", "source"])
    parser.add_argument("--run-id", required=True, help="Correlation label shared with the other machine's run")
    args = parser.parse_args()

    role = MachineRole.TARGET if args.role == "target" else MachineRole.SOURCE
    RoleRunner.run(role, args.run_id)
    print(f"RoleRunner complete for role={args.role!r}, run_id={args.run_id!r}.")
