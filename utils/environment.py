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
}


def resolve(name: str) -> Callable:
    try:
        return STEPS[name]
    except KeyError:
        raise EnvironmentStepError(f"unknown environment step {name!r} (known: {sorted(STEPS)})") from None
