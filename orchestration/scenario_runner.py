"""State-machine scenario runner -- the entry point for YAML-driven scenarios.

    python -m orchestration.scenario_runner --role target --run-id <id> --scenario full_transfer
    python -m orchestration.scenario_runner --role source --run-id <id> --scenario full_transfer
    python -m orchestration.scenario_runner --scenario full_transfer --validate-only

--scenario is a name under scenarios/ (full_transfer -> scenarios/full_transfer.yaml) or a
path. Both machines run this as fully independent processes with the same --run-id and
only ever meet through the Coordination Service (CLAUDE.md "Both machines, one channel").

Compared with orchestration/role_runner.py (the original hand-written flows, kept
untouched): the screen sequence and the dialog policies come from the YAML file, the
waiting/polling comes from orchestration/statemachine/runner.py, and which assertions/
components back each state comes from target_model.py / source_model.py. Prerequisites,
Session launch/teardown, reporting and credentials are handled exactly as role_runner
does them.

Environment (same variables as role_runner; see README):
  Target: DDA_TARGET_BUILD_PATH, DDA_TARGET_SIGNIN_USERNAME, DDA_TARGET_SIGNIN_PASSWORD,
          DDA_TARGET_OTP_STATIC_VALUE, DDA_CDM_SIMULATOR_PATH (--launch simulator only)
  Source: DDA_SOURCE_BUILD_PATH
  Both:   DDA_COORDINATION_SERVICE_URL
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from factory.config import SOURCE_PROCESS_NAME, TARGET_PROCESS_NAME
from factory.logger_factory import LoggerFactory
from factory.session import MachineRole, Session
from orchestration.statemachine import peer, source_model, target_model
from orchestration.statemachine.context import RunContext
from orchestration.statemachine.model import Model
from orchestration.statemachine.observer import (
    HybridObserver,
    ProbeObserver,
    SnapshotObserver,
)
from orchestration.statemachine.runner import PeerFailed, Runner, RunnerError
from orchestration.statemachine.scenario import (
    Scenario,
    ScenarioError,
    lint_scenario,
    load_scenario,
    validate_scenario,
)
from reports.action_reporter import ActionReporter
from reports.html_report_builder import build_report
from utils import environment
from utils.coordination_client import PAIRING_CODE_KEY, CoordinationClient
from utils.prerequisites import ensure_prerequisites

SCENARIO_DIR = Path(__file__).resolve().parent.parent / "scenarios"
MODEL_BUILDERS = {"target": target_model.build, "source": source_model.build}


def resolve_scenario_path(name_or_path: str) -> Path:
    candidate = Path(name_or_path)
    if candidate.suffix in (".yaml", ".yml") or candidate.exists():
        return candidate
    return SCENARIO_DIR / f"{name_or_path}.yaml"


def build_models(app_session=None, roles=None) -> dict[str, Model]:
    roles = roles or list(MODEL_BUILDERS)
    return {role: MODEL_BUILDERS[role](app_session) for role in roles if role in MODEL_BUILDERS}


def load_and_validate(name_or_path: str) -> Scenario:
    path = resolve_scenario_path(name_or_path)
    if not path.exists():
        raise ScenarioError(f"scenario file not found: {path}")
    scenario = load_scenario(path)
    validate_scenario(scenario, build_models(None, list(scenario.roles)))
    return scenario


def _env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k.startswith("DDA_")}


def _require(env: dict[str, str], name: str) -> str:
    value = env.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


def _launch_session(role: MachineRole, env: dict[str, str], launch_mode: str) -> Session:
    if role is MachineRole.TARGET:
        simulator_path = _require(env, "DDA_CDM_SIMULATOR_PATH") if launch_mode == "simulator" else None
        return Session.get(role, build_path=_require(env, "DDA_TARGET_BUILD_PATH"),
                           launch_mode=launch_mode, simulator_path=simulator_path)
    return Session.get(role, build_path=_require(env, "DDA_SOURCE_BUILD_PATH"))


def _run_environment_steps(names, ctx, phase: str) -> None:
    for name in names:
        step = environment.resolve(name)
        ctx.log.info(f"{phase}: {name}")
        try:
            step(ctx)
        except Exception as exc:
            if phase == "setup":
                raise
            ctx.log.error(f"teardown step {name} failed: {exc}")  # keep tearing down


def run(role_name: str, run_id: str, scenario: Scenario, launch_mode: str, observer_kind: str,
        skip_prerequisites: bool = False) -> None:
    role = MachineRole(role_name)
    script = scenario.role(role_name)
    env = _env()
    log = LoggerFactory.get_logger(role_name)

    if not skip_prerequisites:
        ensure_prerequisites()
    ActionReporter.start_run(run_id, role_name)
    reporter = ActionReporter.current()
    reporter.set_test_name(scenario.name)

    session = _launch_session(role, env, launch_mode)
    ctx = RunContext(role=role_name, run_id=run_id, session=session, app=session.app,
                     coordination=CoordinationClient(), log=log, env=env, scenario_name=scenario.name)
    peer_role = "source" if role_name == "target" else "target"
    waited_keys, published_keys = coordination_keys(script)
    own_keys = [f"{role_name}_state", *sorted(published_keys)] + ([PAIRING_CODE_KEY] if role_name == "source" else [])
    peer.clear_own_keys(ctx, own_keys)               # a reused run id starts clean for the other side
    for key in [f"{peer_role}_state", PAIRING_CODE_KEY, *sorted(waited_keys)]:
        peer.snapshot_stale_value(ctx, key)          # whatever the peer left behind before IT clears its keys
    if role_name == "target":
        target_model.snapshot_stale_pairing_code(ctx)
    for key in [f"{role_name}_state", *sorted(published_keys)]:
        peer.publish(ctx, key, "started")
    ctx.scratch["app_process_name"] = SOURCE_PROCESS_NAME if role is MachineRole.SOURCE else TARGET_PROCESS_NAME
    model = MODEL_BUILDERS[role_name](session.app)
    observers = {"hybrid": HybridObserver, "snapshot": SnapshotObserver, "probe": ProbeObserver}
    observer = observers[observer_kind](model)
    outcome = "failed"
    try:
        _run_environment_steps(script.setup, ctx, "setup")
        try:
            Runner(model, script, ctx, observer, reporter=reporter).run()
        except (PeerFailed, peer.PeerFailed) as exc:
            # the OTHER machine failed; this app is healthy and merely waiting, so it
            # can still be closed the way a user would before the all-or-nothing kill
            log.error(f"Scenario {scenario.name!r} ({role_name}) stopped: {exc}")
            _close_app_gracefully(model, ctx)
            raise
        outcome = "finished"
        log.success(f"Scenario {scenario.name!r} ({role_name}) PASSED")
        _close_app_gracefully(model, ctx)
    finally:
        # tell the other machine how this side ended (per explicit user direction,
        # 2026-10-20: the Source must not close until the Target is done)
        peer.publish(ctx, f"{role_name}_state", outcome)
        try:
            _run_environment_steps(script.teardown, ctx, "teardown")
        finally:
            session.close()
            build_report()


def _close_app_gracefully(model: Model, ctx: RunContext) -> None:
    """After a PASSED run, close the app the way a user does (the model's close_app
    action: caption Close / Close button, prompts answered, process exit awaited) so
    Session.close()'s process kill finds nothing left to kill. A failed run keeps the
    old all-or-nothing kill: the app may be mid-transfer, and the close prompts there
    are a finding, not cleanup. Failures here are logged, never fatal."""
    action = next((s.actions["close_app"] for s in model.states.values() if "close_app" in s.actions), None)
    if action is None:
        return
    try:
        ctx.log.info("closing the app gracefully")
        action.perform(ctx, {})
    except Exception as exc:  # noqa: BLE001 -- Session.close() below still stops everything
        ctx.log.warning(f"graceful close failed ({exc}) -- Session.close() will stop the process")


def coordination_keys(script) -> tuple[set, set]:
    """Custom coordination keys a role script reads (wait_for_peer key: / when: key:)
    and publishes (publish key:), so stale values from an earlier run with the same id
    are ignored and our own leftovers are overwritten before any step runs -- the same
    protection <role>_state and pairing_code already have."""
    waited, published = set(), set()
    for step in script.steps:
        if step.when is not None:
            waited.add(str(step.when["key"]))
        key = step.args.get("key")
        if key and step.do == "wait_for_peer":
            waited.add(str(key))
        if key and step.do == "publish":
            published.add(str(key))
    return waited, published


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--scenario", required=True, help="scenario name under scenarios/ or a YAML path")
    parser.add_argument("--role", choices=["target", "source"])
    parser.add_argument("--run-id")
    parser.add_argument("--launch", choices=["exe", "mock", "simulator"],
                        help="Target launch mode (default: the scenario's 'launch', else exe)")
    parser.add_argument("--observer", choices=["hybrid", "snapshot", "probe"], default="hybrid",
                        help="hybrid (default) = one page_source per tick, falling back to per-locator probing "
                             "when /source fails or recognises nothing; snapshot / probe = that one method only")
    parser.add_argument("--validate-only", action="store_true", help="load + validate the scenario, launch nothing")
    parser.add_argument("--skip-prerequisites", action="store_true")
    args = parser.parse_args(argv)

    try:
        scenario = load_and_validate(args.scenario)
    except ScenarioError as exc:
        print(f"INVALID SCENARIO: {exc}", file=sys.stderr)
        return 2
    print(f"Scenario {scenario.name!r} valid for roles {sorted(scenario.roles)}")
    for warning in lint_scenario(scenario, build_models(None, list(scenario.roles))):
        print(f"WARNING: {warning}")
    if args.validate_only:
        return 0
    if not args.role or not args.run_id:
        parser.error("--role and --run-id are required unless --validate-only")

    launch_mode = args.launch or scenario.launch or "exe"
    try:
        run(args.role, args.run_id, scenario, launch_mode, args.observer, args.skip_prerequisites)
    except RunnerError as exc:
        print(f"SCENARIO FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
