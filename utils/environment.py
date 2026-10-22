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

def open_notepad(ctx) -> None:
    """Gives the close-applications precheck something to find."""
    subprocess.Popen(["notepad.exe"])
    time.sleep(2.0)
    ctx.log.info("environment: started notepad.exe so the Close applications dialog has something to close")


def close_notepad(ctx) -> None:
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


def disable_network(ctx) -> None:
    """Drops this PC's network -- raises the noNetwork overlay. Needs admin."""
    name = _adapter_name(ctx)
    _powershell(f"Disable-NetAdapter -Name '{name}' -Confirm:$false")
    ctx.log.warning(f"environment: network adapter {name!r} DISABLED")


def enable_network(ctx) -> None:
    name = ctx.scratch.get("network_adapter") or _adapter_name(ctx)
    _powershell(f"Enable-NetAdapter -Name '{name}' -Confirm:$false")
    ctx.log.info(f"environment: network adapter {name!r} enabled")


def set_network_public(ctx) -> None:
    """Makes the trust-network precheck fail (TrustRequired). Needs admin."""
    _powershell("Get-NetConnectionProfile | Set-NetConnectionProfile -NetworkCategory Public")
    ctx.log.warning("environment: network profile set to Public")


def set_network_private(ctx) -> None:
    _powershell("Get-NetConnectionProfile | Set-NetConnectionProfile -NetworkCategory Private")
    ctx.log.info("environment: network profile set to Private")


# --------------------------------------------------------------------- region

def set_region_unsupported(ctx) -> None:
    """Sets the Windows home location to one the app's supported-region list does not
    include (GeoId 4 = Afghanistan) -- raises localeNotSupported. The previous value is
    kept in scratch for restore_region()."""
    ctx.scratch["geo_id"] = _powershell("(Get-WinHomeLocation).GeoId")
    _powershell("Set-WinHomeLocation -GeoId 4")
    ctx.log.warning("environment: Windows home location set to an unsupported region")


def restore_region(ctx) -> None:
    geo = ctx.scratch.get("geo_id") or ctx.env.get("DDA_HOME_GEOID", "244")  # 244 = United States
    _powershell(f"Set-WinHomeLocation -GeoId {geo}")
    ctx.log.info(f"environment: Windows home location restored to GeoId {geo}")


# --------------------------------------------------------------------- validation

def validate_migration_report(ctx) -> None:
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


def start_benchmark(ctx) -> None:
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


def stop_benchmark_report(ctx) -> None:
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
}


def resolve(name: str) -> Callable:
    try:
        return STEPS[name]
    except KeyError:
        raise EnvironmentStepError(f"unknown environment step {name!r} (known: {sorted(STEPS)})") from None
