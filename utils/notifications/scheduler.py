"""
Registers utils/notifications/listener.py as a Windows Scheduled Task so it survives a
shutdown/reboot and keeps constantly watching for toast notifications, per explicit user
direction (2026-10-19): "listener must work even when laptop is shutdown and opened
later on it must also work when system restarts and constantly keep an eye on toast
notifications... use windows task scheduler to keep the process running and alive and to
start process whenever system is restarted."

Trigger is "At log on" for the CURRENT user, not "At startup"/SYSTEM: the listener's
winsdk/WinRT UserNotificationListener calls need to run in a real interactive user
session (confirmed live -- it was only ever run and tested as the logged-in user;
nothing here has been tried or confirmed running as the SYSTEM account, which
"At startup" would use). "At log on" still satisfies "survives a reboot" -- a reboot
always produces a fresh logon, which re-fires this trigger.

Settings:
  - No execution time limit -- Task Scheduler kills a task after 72 hours by default;
    this listener is meant to run indefinitely ("keep the process running and alive").
  - Restarts automatically on failure (up to 999 times, 1 minute apart) -- if the
    listener process itself crashes, Task Scheduler brings it back rather than silently
    leaving nothing watching.
  - Allowed to run on battery and not stopped if the machine switches to battery -- a
    laptop losing AC power shouldn't silently disable the reminder watcher.
  - StartWhenAvailable -- if the trigger time was missed, it still starts as soon as
    possible rather than waiting for the next logon.

Usage:
    uv run python -m utils.notifications.scheduler
    uv run python -m utils.notifications.scheduler --poll-interval 10
    uv run python -m utils.notifications.scheduler --unregister
    uv run python -m utils.notifications.scheduler --start-now

Registering/unregistering a Scheduled Task is a persistent, machine-wide change (it
will keep auto-starting the listener at every future logon until removed) -- run
--unregister to take it back out.
"""

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TASK_NAME = "DellNotificationListener"


def _run_powershell(script: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        capture_output=True, text=True, timeout=30,
    )


def is_registered() -> bool:
    result = _run_powershell(
        f"if (Get-ScheduledTask -TaskName '{TASK_NAME}' -ErrorAction SilentlyContinue) {{ 'yes' }}"
    )
    return result.stdout.strip() == "yes"


def unregister() -> None:
    _run_powershell(f"Unregister-ScheduledTask -TaskName '{TASK_NAME}' -Confirm:$false -ErrorAction SilentlyContinue")
    print(f"Unregistered scheduled task {TASK_NAME!r} (if it existed).")


def register(poll_interval: float) -> None:
    # Bug fixed here, confirmed live (2026-10-19): Register-ScheduledTask requires
    # elevation -- a plain (non-elevated) PowerShell session fails with "Access is
    # denied" (HRESULT 0x80070005), but that error did NOT stop the rest of a -Command
    # string from running, so an earlier version's own success message printed even
    # though the task was never created. Now runs the whole registration elevated via
    # Start-Process -Verb RunAs -Wait, and verifies success afterward via
    # Get-ScheduledTask rather than trusting the elevated child's own output.
    #
    # Also confirmed live: a bare 'uv' -Execute value failed with LastTaskResult
    # 2147942402 ("file not found") -- Task Scheduler's launch context doesn't resolve
    # PATH the way an interactive shell does. Resolving uv's absolute path ourselves
    # fixes it.
    uv_path = shutil.which("uv")
    if not uv_path:
        raise RuntimeError("Could not resolve 'uv' on PATH -- install it or ensure it's discoverable before registering this task")

    # uv run needs the repo as cwd -- the action's -WorkingDirectory does that, not a
    # `cd` baked into the argument string itself.
    argument = f"run python -m utils.notifications.listener --poll-interval {poll_interval}"
    # Bug fixed here, confirmed live: passing a multi-statement script as a single
    # -ArgumentList '...','-Command','<script>' string broke, because the script itself
    # contains single quotes -- the OUTER single-quote wrapping terminated early at the
    # first one, mangling the command. Writing it to a real .ps1 file and invoking that
    # via -File sidesteps the whole class of escaping problems -- same pattern
    # factory/session.py already uses for its own embedded scripts, for the identical
    # reason.
    inner_script = f"""
$action = New-ScheduledTaskAction -Execute '{uv_path}' -Argument '{argument}' -WorkingDirectory '{REPO_ROOT}'
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
Register-ScheduledTask -TaskName '{TASK_NAME}' -Action $action -Trigger $trigger -Settings $settings -Description 'Watches for toast notifications and dispatches an assigned automation flow (dell-automation repo, notification-automation feature)' -Force
"""
    script_path = Path(tempfile.gettempdir()) / "dda_register_notification_listener_task.ps1"
    script_path.write_text(inner_script, encoding="utf-8")
    _run_powershell(
        "Start-Process powershell -Verb RunAs -ArgumentList "
        f"'-NoProfile','-ExecutionPolicy','Bypass','-File','{script_path}' -Wait"
    )
    if not is_registered():
        raise RuntimeError(
            "Scheduled task was not found after attempting registration -- the elevation "
            "prompt may have been denied, or Register-ScheduledTask failed for another "
            "reason. Re-run and check for a UAC prompt needing approval."
        )
    print(f"Registered scheduled task {TASK_NAME!r}:")
    print(f"  Action: {uv_path} {argument}")
    print(f"  Working directory: {REPO_ROOT}")
    print("  Trigger: at logon (current user) -- fires again after every reboot's fresh logon")
    print("  Restarts automatically on failure (up to 999x, 1 min apart); no execution time limit")
    print()
    print("To start it right now without waiting for the next logon: uv run python -m utils.notifications.scheduler --start-now")
    print("To remove it: uv run python -m utils.notifications.scheduler --unregister")


def start_now() -> None:
    result = _run_powershell(f"Start-ScheduledTask -TaskName '{TASK_NAME}'")
    if result.returncode != 0:
        raise RuntimeError(f"Failed to start scheduled task -- stderr={result.stderr!r}")
    print(f"Started scheduled task {TASK_NAME!r} now.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument("--unregister", action="store_true", help="Remove the scheduled task instead of creating it")
    parser.add_argument("--start-now", action="store_true", help="Start the already-registered task immediately")
    args = parser.parse_args()

    if args.unregister:
        unregister()
    elif args.start_now:
        start_now()
    else:
        register(args.poll_interval)
        print(f"\nCurrently registered: {is_registered()}")
