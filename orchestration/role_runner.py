"""
RoleRunner: the real entry point for one independent automation process -- chains this
machine's own role (Target or Source) through a scenario's flow sequence, given a role,
a run_id shared between the two independent processes/machines, and a scenario name.
See PROJECT_PLAN.md Sec 4.6.

`tools/*.py` scripts are dev/debug helpers only (manual, piecemeal testing of one flow
or component at a time, used throughout Phase 0-3 development) -- this is the one
command meant for actually running a role end to end in production, chaining its real
flows together rather than poking at internals.

Scenario dispatch (2026-10-08, per explicit user direction): TargetRunner/SourceRunner
each own only their own role's FIXED prefix -- sign-in + pairing for Target, pairing
for Source -- the part every scenario shares identically, with no exceptions. What
happens after pairing succeeds is a list of plain `(session) -> None` step functions,
supplied by a scenario function (e.g. full_transfer() below) that decides, per role,
which steps apply. Adding a new scenario means: write its step function(s), write one
small scenario function that picks steps per role and calls RoleRunner.run(), add one
entry to SCENARIOS -- no change to TargetRunner, SourceRunner, or RoleRunner itself.
This assumes every scenario shares the exact same prefix; a scenario that needs to
diverge BEFORE pairing finishes (e.g. sign-in only, no pairing attempt) doesn't fit
this shape and would need its own prefix too, not just a new step list.

Usage:
    python -m orchestration.role_runner --role target --run-id my-migration
    python -m orchestration.role_runner --role source --run-id my-migration
    python -m orchestration.role_runner --role target --run-id my-migration --scenario full_transfer

Both machines must be given the SAME run_id -- a plain correlation label (not a secret),
agreed on by whoever starts the two independent runs (see utils/coordination_client.py).
Both machines should also be given the SAME --scenario name, by the same convention --
nothing in code enforces this (the two processes never see each other's arguments),
but a scenario's Target-side and Source-side step functions are written as
complementary halves of one story, so a mismatch (e.g. Target running full_transfer
while Source runs a different scenario) won't error at pairing time -- it'll surface
later as one side timing out waiting for a screen the other side's scenario never
produces.

Env vars (role-specific, see each Runner class below):
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
from typing import Callable, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.coordination_client import CoordinationClient
from utils.prerequisites import ensure_prerequisites
from factory.session import MachineRole, Session
from flows.source.pairing_flow import SourcePairingFlow
from flows.source.transfer_flow import SourceTransferFlow
from flows.target.authentication.sign_in_flow import SignInFlow
from flows.target.pairing_flow import TargetPairingFlow
from flows.target.transfer_flow import TargetTransferFlow
from reports.action_reporter import ActionReporter
from reports.html_report_builder import build_report


class RoleRunnerError(Exception):
    pass


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RoleRunnerError(
            f"Missing required environment variable {name}. Set it (e.g. in .env) and re-run."
        )
    return value


class TargetRunner:
    """Owns only the Target role's fixed prefix (sign-in + pairing) -- the part every
    Target scenario shares identically. Whatever happens after pairing succeeds is
    entirely up to post_pairing_steps, supplied by whichever scenario function called
    this."""

    @staticmethod
    def run(run_id: str, post_pairing_steps: List[Callable[[Session], None]]) -> None:
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

            for step in post_pairing_steps:
                step(session)
        finally:
            # Bug fixed here, confirmed live (2026-10-07): this used to be
            # except BaseException: session.close(); raise, which only ever closed
            # WinAppDriver and the app on FAILURE -- a fully successful run just fell
            # through and left both running indefinitely, with no cleanup at all,
            # confirmed directly by the user's own question about this. finally runs
            # on both success and failure; Session.close() is already safe to call
            # unconditionally (every step inside it already handles "nothing to clean
            # up" gracefully), so this needs no other change.
            session.close()


class SourceRunner:
    """Owns only the Source role's fixed prefix (pairing) -- the part every Source
    scenario shares identically. Whatever happens after pairing succeeds is entirely up
    to post_pairing_steps, supplied by whichever scenario function called this."""

    @staticmethod
    def run(run_id: str, post_pairing_steps: List[Callable[[Session], None]]) -> None:
        build_path = _require_env("DDA_SOURCE_BUILD_PATH")

        session = Session.get(MachineRole.SOURCE, build_path=build_path)
        try:
            coordination_client = CoordinationClient()
            flow = SourcePairingFlow(session.app, run_id=run_id, coordination_client=coordination_client)
            flow.run()

            for step in post_pairing_steps:
                step(session)
        finally:
            # See TargetRunner.run()'s matching comment -- finally guarantees cleanup on
            # both success and failure, not just failure.
            session.close()


class RoleRunner:
    @staticmethod
    def run(role: MachineRole, run_id: str, runner_class, post_pairing_steps: List[Callable[[Session], None]]) -> None:
        """The thin, universal wrapper -- the one place prerequisites/reporting happen,
        exactly once, regardless of role or scenario. Does not branch on role itself:
        by the time a scenario function calls this, it has already resolved role into a
        concrete runner_class (TargetRunner or SourceRunner) and the step list that
        applies to it."""
        # Standalone machine-level setup gate (dev mode, WinAppDriver installed +
        # launchable, Python packages, browser cleanup) -- same checks regardless of
        # role. Lives in utils/, not in factory/ (see its own module docstring,
        # 2026-10-07). Does not leave WinAppDriver running: Session, created below,
        # launches its own independently via factory.driver_factory, the moment it's
        # actually needed.
        ensure_prerequisites()
        ActionReporter.start_run(run_id, role.value)

        try:
            runner_class.run(run_id, post_pairing_steps)
        finally:
            # A report must exist for this run whether it succeeded or failed -- see
            # PROJECT_PLAN.md Sec 4.8.
            build_report()


# ---------------------------------------------------------------------------------
# Scenarios. Each post-pairing step function is a plain (session) -> None callable;
# each scenario function decides, per role, which runner class and step list apply.
# ---------------------------------------------------------------------------------

def full_transfer_target(session: Session) -> None:
    transfer_flow = TargetTransferFlow(session.app)
    transfer_flow.start_transfer()
    transfer_flow.wait_for_completion()


def full_transfer_source(session: Session) -> None:
    transfer_flow = SourceTransferFlow(session.app)
    transfer_flow.wait_for_transfer_to_start()
    transfer_flow.wait_for_migration_to_complete()


def full_transfer(role: MachineRole, run_id: str) -> None:
    """The one scenario that exists today: the shared prefix (sign-in + pairing for
    Target, pairing for Source), then a complete file transfer, for whichever role this
    process is."""
    if role is MachineRole.TARGET:
        RoleRunner.run(role, run_id, TargetRunner, [full_transfer_target])
    else:
        RoleRunner.run(role, run_id, SourceRunner, [full_transfer_source])


SCENARIOS = {
    "full_transfer": full_transfer,
}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", required=True, choices=["target", "source"])
    parser.add_argument("--run-id", required=True, help="Correlation label shared with the other machine's run")
    parser.add_argument(
        "--scenario", default="full_transfer", choices=list(SCENARIOS),
        help="Which post-pairing flow sequence to run (default: full_transfer). "
             "Both machines should be given the same scenario name.",
    )
    args = parser.parse_args()

    role = MachineRole.TARGET if args.role == "target" else MachineRole.SOURCE
    SCENARIOS[args.scenario](role, args.run_id)
    print(f"RoleRunner complete for role={args.role!r}, run_id={args.run_id!r}, scenario={args.scenario!r}.")
