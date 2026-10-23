"""Environment setup/teardown steps a scenario can name in its `setup:` / `teardown:`
lists (see orchestration/statemachine/scenario.py). Each is a plain function taking the
RunContext; names are resolved through STEPS.

These put the *machine* into the state a scenario needs -- something the UI runner
cannot do from inside the app: a running application for the close-apps dialog, a
dropped network adapter for the network-loss dialogs, a Public network profile for the
trust-network dialog. Most need an elevated PowerShell and are only meaningful on the
real hardware; none has been confirmed live yet (2026-10-19) -- they are written from
the Windows cmdlet documentation and should be verified on the first run that uses
them.

Add a step: write the function, register it in STEPS. Keep steps idempotent and give
each one a matching undo so a scenario's teardown can restore the machine.
"""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

PS_TIMEOUT_SECONDS = 60


class EnvironmentStepError(Exception):
    pass


def _powershell(command: str, timeout: int = PS_TIMEOUT_SECONDS) -> str:
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
        capture_output=True, text=True, timeout=timeout,
    )
    if completed.returncode != 0:
        raise EnvironmentStepError(
            f"PowerShell step failed ({completed.returncode}): {command}\n{completed.stderr.strip()}"
        )
    return completed.stdout.strip()


# --------------------------------------------------------------------- applications

def open_notepad(ctx, args=None) -> None:
    """Gives the close-applications precheck something to find."""
    subprocess.Popen(["notepad.exe"])
    time.sleep(2.0)
    ctx.log.info("environment: started notepad.exe so the Close applications dialog has something to close")


def close_notepad(ctx, args=None) -> None:
    _powershell("Get-Process notepad -ErrorAction SilentlyContinue | Stop-Process -Force")
    ctx.log.info("environment: notepad.exe stopped")


# --------------------------------------------------------------------- network

def _adapter_name(ctx) -> str:
    name = ctx.env.get("DDA_NETWORK_ADAPTER_NAME")
    if name:
        return name
    # the adapter currently carrying the default route
    name = _powershell(
        "(Get-NetRoute -DestinationPrefix '0.0.0.0/0' | Sort-Object RouteMetric | "
        "Select-Object -First 1 | Get-NetAdapter).Name"
    )
    if not name:
        raise EnvironmentStepError("could not determine the active network adapter; set DDA_NETWORK_ADAPTER_NAME")
    ctx.scratch["network_adapter"] = name
    return name


def disable_network(ctx, args=None) -> None:
    """Drops this PC's network -- raises the noNetwork overlay. Needs admin."""
    name = _adapter_name(ctx)
    _powershell(f"Disable-NetAdapter -Name '{name}' -Confirm:$false")
    ctx.log.warning(f"environment: network adapter {name!r} DISABLED")


def enable_network(ctx, args=None) -> None:
    name = ctx.scratch.get("network_adapter") or _adapter_name(ctx)
    _powershell(f"Enable-NetAdapter -Name '{name}' -Confirm:$false")
    ctx.log.info(f"environment: network adapter {name!r} enabled")


def set_network_public(ctx, args=None) -> None:
    """Makes the trust-network precheck fail (TrustRequired). Needs admin."""
    _powershell("Get-NetConnectionProfile | Set-NetConnectionProfile -NetworkCategory Public")
    ctx.log.warning("environment: network profile set to Public")


def set_network_private(ctx, args=None) -> None:
    _powershell("Get-NetConnectionProfile | Set-NetConnectionProfile -NetworkCategory Private")
    ctx.log.info("environment: network profile set to Private")


# --------------------------------------------------------------------- region

def set_region_unsupported(ctx, args=None) -> None:
    """Sets the Windows home location to one the app's supported-region list does not
    include (GeoId 4 = Afghanistan) -- raises localeNotSupported. The previous value is
    kept in scratch for restore_region()."""
    ctx.scratch["geo_id"] = _powershell("(Get-WinHomeLocation).GeoId")
    _powershell("Set-WinHomeLocation -GeoId 4")
    ctx.log.warning("environment: Windows home location set to an unsupported region")


def restore_region(ctx, args=None) -> None:
    geo = ctx.scratch.get("geo_id") or ctx.env.get("DDA_HOME_GEOID", "244")  # 244 = United States
    _powershell(f"Set-WinHomeLocation -GeoId {geo}")
    ctx.log.info(f"environment: Windows home location restored to GeoId {geo}")


# --------------------------------------------------------------------- validation

def validate_migration_report(ctx, args=None) -> None:
    """Runs validation/validate_migration.py against the newest MigrationReport PDF on
    this (Target) PC: every file the report claims was copied must exist, and every
    registry-backed setting must match. Writes the usual validation/output HTML and
    fails the scenario if anything checkable did not match. Added as a scenario step
    per explicit user direction (2026-10-20); the standalone CLI still works unchanged."""
    from validation.validate_migration import run as validate

    report = ctx.env.get("DDA_MIGRATION_REPORT_PATH")
    ctx.log.info("validation: checking the migration report against this PC" + (f" ({report})" if report else ""))
    ok = validate(report_path=report, write_html=True)
    if not ok:
        raise EnvironmentStepError("migration-report validation FAILED -- see validation/output/ for the HTML report")
    ctx.log.success("validation: migration report matches this PC")


# --------------------------------------------------------------------- benchmark

BENCHMARK_STOP_WAIT_SECONDS = 15


def start_benchmark(ctx, args=None) -> None:
    """Target setup: launches the benchmark resource sampler as its own subprocess (see
    benchmark/resource_sampler.py, BENCHMARKING_PLAN.md). Never blocks and never raises: a
    sampler that fails to start only costs the report its resource tabs."""
    try:
        import sys
        from pathlib import Path

        from benchmark import paths

        env = {**os.environ, **(ctx.env or {})}
        out = paths.prepare_output_dir(ctx.run_id)
        stop_file = out / f"STOP_{ctx.role}"
        cmd = [
            sys.executable, "-m", "benchmark.resource_sampler",
            "--run-id", ctx.run_id, "--role", ctx.role, "--out", str(out),
            "--interval", str(paths.interval(env)), "--stop-file", str(stop_file),
            "--processes", ",".join(paths.processes(env)),
        ]
        log_file = (out / f"sampler_{ctx.role}.log").open("w", encoding="utf-8")
        proc = subprocess.Popen(cmd, cwd=str(Path(__file__).resolve().parent.parent),
                                stdout=log_file, stderr=subprocess.STDOUT)
        ctx.scratch["benchmark"] = {"proc": proc, "out": out, "stop_file": stop_file, "log_file": log_file}
        ctx.log.info(f"benchmark: resource sampler started (pid {proc.pid}) -> {out}")
    except Exception as exc:
        ctx.log.warning(f"benchmark: could not start the resource sampler: {exc}")


def stop_benchmark_report(ctx, args=None) -> None:
    """Target teardown: stops the sampler, harvests CDM.db / the rclone log / the samples and
    renders benchmark/output/<run_id>/report_<role>.html. MUST NEVER RAISE -- it runs in the
    scenario's guaranteed teardown, so every failure is logged and swallowed."""
    try:
        from benchmark import correlate, harvest, paths, report

        env = {**os.environ, **(ctx.env or {})}
        state = ctx.scratch.get("benchmark") or {}
        out = state.get("out") or paths.output_dir(ctx.run_id)
        _stop_sampler(ctx, state)
        run_report = harvest.harvest_run(ctx.run_id, ctx.role, out, env)
        correlate.annotate(run_report, env)
        html = report.render(run_report, out / f"report_{ctx.role}.html")
        ctx.log.success(f"benchmark: report written to {html}")
    except BaseException as exc:  # noqa: BLE001 -- teardown safety: nothing may escape
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        try:
            ctx.log.warning(f"benchmark: report not produced: {exc}")
        except Exception:
            pass


def _stop_sampler(ctx, state: dict) -> None:
    """Touches the stop file, waits briefly for a clean exit, terminates as a backstop."""
    try:
        stop_file = state.get("stop_file")
        if stop_file is not None:
            stop_file.write_text("stop", encoding="utf-8")
        proc = state.get("proc")
        if proc is not None:
            try:
                proc.wait(timeout=BENCHMARK_STOP_WAIT_SECONDS)
            except subprocess.TimeoutExpired:
                ctx.log.warning("benchmark: sampler did not exit on the stop file; terminating it")
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
        log_file = state.get("log_file")
        if log_file is not None:
            log_file.close()
    except Exception as exc:
        ctx.log.warning(f"benchmark: error while stopping the sampler: {exc}")


# --------------------------------------------------------------------- test data

# The PowerShell seeding scripts under testdata/ (see testdata/README.md). These steps
# wrap them so a scenario can generate its own migration test data from the YAML, and
# clean it up in teardown. Each step's YAML `args:` map is translated into script
# parameters, so all seeding input lives in the scenario file.
_TESTDATA_DIR = Path(__file__).resolve().parent.parent / "testdata"
TESTDATA_DEFAULT_TIMEOUT_SECONDS = 1800  # a Stress profile (2 GB + 5000 files) takes a while


def _run_testdata_script(ctx, script_name: str, script_args: list[str], timeout: int) -> None:
    script = _TESTDATA_DIR / script_name
    if not script.is_file():
        raise EnvironmentStepError(f"test-data script not found: {script}")
    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *script_args]
    ctx.log.info("environment: " + " ".join(cmd))
    try:
        completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise EnvironmentStepError(f"{script_name} timed out after {timeout}s") from exc
    tail = "\n".join((completed.stdout or "").strip().splitlines()[-8:])
    if tail:
        ctx.log.info(f"{script_name} output (tail):\n{tail}")
    if completed.returncode != 0:
        raise EnvironmentStepError(
            f"{script_name} failed ({completed.returncode}): {(completed.stderr or completed.stdout).strip()}"
        )


def _seed_script_args(args: dict | None) -> list[str]:
    """Translates a scenario step's args map into seed_*.ps1 parameters.
    Recognised keys: profile, many_small_count, big_file_mb, include_locked,
    lock_minutes, dry_run."""
    args = args or {}
    out: list[str] = []
    if args.get("profile"):            out += ["-Profile", str(args["profile"])]
    if args.get("many_small_count") is not None: out += ["-ManySmallCount", str(int(args["many_small_count"]))]
    if args.get("big_file_mb") is not None:      out += ["-BigFileMB", str(args["big_file_mb"])]
    if args.get("include_locked"):     out += ["-IncludeLocked"]
    if args.get("lock_minutes") is not None:     out += ["-LockMinutes", str(int(args["lock_minutes"]))]
    if args.get("dry_run"):            out += ["-DryRun"]
    return out


def _testdata_timeout(args: dict | None) -> int:
    args = args or {}
    return int(args.get("script_timeout") or TESTDATA_DEFAULT_TIMEOUT_SECONDS)


def seed_source_data(ctx, args=None) -> None:
    """Seeds the SOURCE PC's migration test data (testdata/seed_source.ps1)."""
    _run_testdata_script(ctx, "seed_source.ps1", _seed_script_args(args), _testdata_timeout(args))
    ctx.log.success("environment: source test data seeded")


def seed_target_data(ctx, args=None) -> None:
    """Seeds the TARGET PC's pre-existing/colliding test data (testdata/seed_target.ps1)."""
    _run_testdata_script(ctx, "seed_target.ps1", _seed_script_args(args), _testdata_timeout(args))
    ctx.log.success("environment: target test data seeded")


def clean_test_data(ctx, args=None) -> None:
    """Removes all seeded DellMigrateTest data (testdata/clean.ps1 -Force). Teardown-safe."""
    _run_testdata_script(ctx, "clean.ps1", ["-Force"], _testdata_timeout(args))
    ctx.log.info("environment: test data cleaned")


# Coordination key the Source manifest is published under so the Target can fetch it and
# run the permission-retention check without a manual file copy between the two PCs.
SOURCE_MANIFEST_KEY = "source_perm_manifest"


def publish_source_manifest(ctx, args=None) -> None:
    """Source: publishes its seeding manifest (which holds every permission file's captured
    security state) through the Coordination Service, so the Target's check_permissions step
    can fetch it. Run after seed_source_data. args: key, manifest_path."""
    args = args or {}
    key = args.get("key") or SOURCE_MANIFEST_KEY
    manifest = Path(args.get("manifest_path") or (_TESTDATA_DIR / "output" / "source_manifest_latest.json"))
    if not manifest.is_file():
        raise EnvironmentStepError(f"source manifest not found: {manifest} (run seed_source_data first)")
    content = manifest.read_text(encoding="utf-8")
    ctx.coordination.publish(ctx.run_id, key, content)
    ctx.log.success(f"environment: published source manifest ({len(content)} bytes) as {key!r}")


def check_permissions(ctx, args=None) -> None:
    """Target: fetches the Source manifest from the Coordination Service and runs
    testdata/check_permissions.ps1 against the migrated files on this PC. Run after the
    migration completes, before clean_test_data. args: key, fetch_timeout, script_timeout,
    fail_on_change (default true -- a changed/missing permission fails the scenario)."""
    args = args or {}
    key = args.get("key") or SOURCE_MANIFEST_KEY
    fetch_timeout = float(args.get("fetch_timeout") or 300)
    fail_on_change = args.get("fail_on_change", True)

    ctx.log.info(f"environment: waiting for the source manifest ({key!r}) from the peer")
    content = ctx.coordination.wait_for(ctx.run_id, key, timeout=fetch_timeout)
    incoming = _TESTDATA_DIR / "output" / f"incoming_source_manifest_{ctx.run_id}.json"
    incoming.parent.mkdir(parents=True, exist_ok=True)
    incoming.write_text(content, encoding="utf-8")

    try:
        _run_testdata_script(ctx, "check_permissions.ps1",
                             ["-SourceManifest", str(incoming)], _testdata_timeout(args))
        ctx.log.success("environment: permission retention check PASSED")
    except EnvironmentStepError:
        if fail_on_change:
            raise
        ctx.log.warning("environment: permission retention check reported changes "
                        "(fail_on_change=false) -- see testdata/output/permission_check_*.json")


def check_collisions(ctx, args=None) -> None:
    """Target: validates every seeded case (collisions AND edge cases) against the live
    files on this PC after the migration, via testdata/check_collisions.ps1. Fetches the
    Source manifest from the Coordination Service and uses the local Target manifest. Run
    after the migration, before clean_test_data. args: key, fetch_timeout, script_timeout,
    expected_conflict_winner (source|target), require_migrated (bool), fail_on_change
    (default true -- data loss/corruption fails the scenario)."""
    args = args or {}
    key = args.get("key") or SOURCE_MANIFEST_KEY
    fetch_timeout = float(args.get("fetch_timeout") or 300)
    fail_on_change = args.get("fail_on_change", True)

    ctx.log.info(f"environment: waiting for the source manifest ({key!r}) from the peer")
    content = ctx.coordination.wait_for(ctx.run_id, key, timeout=fetch_timeout)
    incoming = _TESTDATA_DIR / "output" / f"incoming_source_manifest_{ctx.run_id}.json"
    incoming.parent.mkdir(parents=True, exist_ok=True)
    incoming.write_text(content, encoding="utf-8")

    target_manifest = _TESTDATA_DIR / "output" / "target_manifest_latest.json"
    if not target_manifest.is_file():
        raise EnvironmentStepError(f"target manifest not found: {target_manifest} (run seed_target_data first)")

    script_args = ["-SourceManifest", str(incoming), "-TargetManifest", str(target_manifest)]
    if args.get("expected_conflict_winner"):
        script_args += ["-ExpectedConflictWinner", str(args["expected_conflict_winner"])]
    if args.get("require_migrated"):
        script_args += ["-RequireMigrated"]

    try:
        _run_testdata_script(ctx, "check_collisions.ps1", script_args, _testdata_timeout(args))
        ctx.log.success("environment: collision + edge-case check PASSED")
    except EnvironmentStepError:
        if fail_on_change:
            raise
        ctx.log.warning("environment: collision/edge check reported issues (fail_on_change=false) "
                        "-- see testdata/output/collision_check_*.json")


# --------------------------------------------------------------------- registry

STEPS: dict[str, Callable] = {
    "open_notepad": open_notepad,
    "close_notepad": close_notepad,
    "disable_network": disable_network,
    "enable_network": enable_network,
    "set_network_public": set_network_public,
    "set_network_private": set_network_private,
    "set_region_unsupported": set_region_unsupported,
    "restore_region": restore_region,
    "validate_migration_report": validate_migration_report,
    "start_benchmark": start_benchmark,
    "stop_benchmark_report": stop_benchmark_report,
    "seed_source_data": seed_source_data,
    "seed_target_data": seed_target_data,
    "clean_test_data": clean_test_data,
    "publish_source_manifest": publish_source_manifest,
    "check_permissions": check_permissions,
    "check_collisions": check_collisions,
}


def resolve(name: str) -> Callable:
    try:
        return STEPS[name]
    except KeyError:
        raise EnvironmentStepError(f"unknown environment step {name!r} (known: {sorted(STEPS)})") from None
