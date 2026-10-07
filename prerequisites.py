"""
Prerequisite checks + auto-install for running WinAppDriver-based automation against the
Target PC app. Target-only (see PROJECT_PLAN.md Sec 10 open item: Source's launch flow is
still undetermined, pending Source PC build access).

Covers, in order: Windows Developer Mode, WinAppDriver installed, that WinAppDriver can
actually launch on this machine, the required Python packages, and browser-profile
cleanup. Node.js (for the GlassFloor mock server, Sec 5.3a) is checked separately via
ensure_mock_server_prerequisites since it's only needed for that launch mode.

Lives at the repo root, not inside factory/ (moved here 2026-10-07, per explicit user
direction): this is a standalone, one-time pass/fail gate run once before automation
starts, not a Factory-layer component -- if all checks pass, automation may proceed; if
not, it must not. factory/driver_factory.py is the sole owner of actually finding,
launching, and killing the real WinAppDriver process ("the actual driver must be yielded
by driver_factory") -- this module calls into those same two functions
(ensure_winappdriver_running()/kill_winappdriver()) for its own one-time launch-then-close
self-test (confirming WinAppDriver CAN run here), then leaves it closed. The real,
long-lived instance actually used for automation is launched independently and later, by
factory.session.Session, via the same driver_factory functions -- this gate never leaves
WinAppDriver running for anything else's benefit.
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import winreg
from pathlib import Path

from factory.config import NODE_INSTALL_PATHS
from factory.driver_factory import ensure_winappdriver_running, find_winappdriver_path, kill_winappdriver

REQUIRED_PACKAGES = {
    "selenium": "selenium",
    "requests": "requests",
}

def _run_powershell(command: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True, text=True, timeout=timeout,
    )


def check_developer_mode() -> bool:
    # Plain winreg, not a PowerShell subprocess -- a subprocess.run call here (even one
    # that just reads the registry) was observed to corrupt later pywin32 imports in the
    # same process (exit code 15, no catchable exception, no crash log) earlier in
    # development. See tools/phase0_inspection_notes.md. (This module no longer imports
    # pywin32 at all, but winreg is kept here regardless -- it's simpler and has no
    # subprocess overhead.)
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\AppModelUnlock",
        )
        value, _ = winreg.QueryValueEx(key, "AllowDevelopmentWithoutDevLicense")
        return value == 1
    except FileNotFoundError:
        return False


def ensure_developer_mode() -> None:
    if check_developer_mode():
        return
    print("Developer Mode is off -- enabling it (this needs one admin approval)...")
    _run_powershell(
        "Start-Process powershell -Verb RunAs -ArgumentList "
        "'-NoProfile','-Command','New-ItemProperty -Path "
        "\"HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\AppModelUnlock\" "
        "-Name \"AllowDevelopmentWithoutDevLicense\" -Value 1 -PropertyType DWORD -Force' -Wait"
    )
    if not check_developer_mode():
        raise RuntimeError("Failed to enable Developer Mode -- was the admin prompt approved?")


def ensure_winappdriver_installed() -> str:
    """Installed-path check only -- uses factory.driver_factory.find_winappdriver_path()
    as the one source of truth for where WinAppDriver lives, rather than re-searching
    independently."""
    path = find_winappdriver_path()
    if path:
        return path
    print("WinAppDriver not found -- installing via winget (this needs one admin approval)...")
    subprocess.run(
        ["winget", "install", "--id", "Microsoft.WindowsApplicationDriver",
         "--source", "winget", "--accept-source-agreements", "--accept-package-agreements", "--silent"],
        timeout=300,
    )
    path = find_winappdriver_path()
    if not path:
        raise RuntimeError("WinAppDriver install did not complete -- was the admin prompt approved?")
    return path


def ensure_winappdriver_can_launch() -> None:
    """One-time self-test: launch WinAppDriver (elevated, via factory.driver_factory),
    confirm it actually came up, then close it right back down. Proves this machine CAN
    run it; does not leave anything running for a later Session to reuse -- Session
    launches its own, independently, via the exact same driver_factory functions, the
    moment it's actually needed.
    """
    print("Verifying WinAppDriver can actually start on this machine (this needs one admin approval)...")
    ensure_winappdriver_running()
    kill_winappdriver()
    print("WinAppDriver: confirmed launchable.")


def find_node() -> str | None:
    # Check common install paths directly, not just PATH -- a process started before a
    # just-completed winget install won't see the updated PATH (same stale-PATH issue
    # observed throughout Phase 0; see tools/phase0_inspection_notes.md).
    found = shutil.which("node")
    if found:
        return found
    for path in NODE_INSTALL_PATHS:
        if Path(path).exists():
            return path
    return None


def ensure_node_installed() -> str:
    path = find_node()
    if path:
        return path
    print("Node.js not found -- installing via winget (this needs one admin approval)...")
    subprocess.run(
        ["winget", "install", "--id", "OpenJS.NodeJS.LTS", "--source", "winget",
         "--accept-source-agreements", "--accept-package-agreements", "--silent"],
        timeout=300,
    )
    path = find_node()
    if not path:
        raise RuntimeError(
            "Node.js install did not complete, or this already-running process can't see "
            "the updated PATH -- was the admin prompt approved? If so, re-run from a fresh "
            "terminal."
        )
    return path


def ensure_mock_server_prerequisites() -> str:
    """Node.js check, separate from ensure_target_prerequisites() since it's only needed
    for the GlassFloor mock-server launch mode, not plain app launches. Returns the
    resolved node.exe path.
    """
    node_path = ensure_node_installed()
    print("Mock server prerequisites OK.")
    return node_path


def check_python_packages() -> list[str]:
    missing = []
    for package_name, import_name in REQUIRED_PACKAGES.items():
        if importlib.util.find_spec(import_name) is None:
            missing.append(package_name)
    return missing


def ensure_python_packages() -> None:
    missing = check_python_packages()
    if not missing:
        return
    print(f"Installing missing Python packages: {', '.join(missing)} ...")
    subprocess.run([sys.executable, "-m", "pip", "install", *missing], check=True)


_BROWSER_PROFILE_PREFERENCES_PATHS = [
    r"Google\Chrome\User Data\Default\Preferences",
    r"Microsoft\Edge\User Data\Default\Preferences",
]


def _mark_browser_profile_as_cleanly_exited(preferences_path: Path) -> None:
    """Patches a Chromium-based browser's profile Preferences file so it believes its
    last session exited normally, preventing the "Chrome didn't shut down correctly" /
    "Restore pages?" dialog on next launch -- confirmed to otherwise interfere with
    automation by stealing keyboard focus mid-typing (see
    components/target/browser_sign_in_page.py's RestorePagesDialog).

    Necessary because our own failure cleanup force-kills the app/browser rather than
    closing it gracefully (see SignInFlow._cleanup_after_failure()), which is exactly
    what sets Chromium's own crash-detection flags in the first place. A launch flag
    (e.g. --restore-last-session=false) isn't an option here: the Dell app launches the
    OS-default browser internally, not this automation, so there's no launch command to
    add flags to -- the profile's own saved state is the only lever available.

    Only touches the two keys that control this specific dialog; every other preference
    (history, passwords, bookmarks, etc.) is read back unchanged and rewritten as-is.
    Silently does nothing if the file doesn't exist or can't be parsed as JSON -- this
    is a best-effort convenience, not a required prerequisite step.
    """
    if not preferences_path.exists():
        return
    try:
        data = json.loads(preferences_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    profile = data.setdefault("profile", {})
    if profile.get("exit_type") == "Normal" and profile.get("exited_cleanly") is True:
        return  # already clean -- don't rewrite the file for no reason
    profile["exit_type"] = "Normal"
    profile["exited_cleanly"] = True
    try:
        preferences_path.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass  # e.g. file locked because the browser is still running -- skip, not fatal


def _disable_autofill_suggestions(preferences_path: Path) -> None:
    """Disables Chromium's address/payment autofill suggestions for the profile the Dell
    sign-in page opens in, so the email field never gets silently prefilled with a saved
    value instead of the username our automation types. Only touches the two autofill
    keys; every other preference is read back unchanged and rewritten as-is. Silently
    does nothing if the file doesn't exist or can't be parsed -- best-effort, not a
    required prerequisite step.
    """
    if not preferences_path.exists():
        return
    try:
        data = json.loads(preferences_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    autofill = data.setdefault("autofill", {})
    if autofill.get("profile_enabled") is False and autofill.get("credit_card_enabled") is False:
        return  # already disabled -- don't rewrite the file for no reason
    autofill["profile_enabled"] = False
    autofill["credit_card_enabled"] = False
    try:
        preferences_path.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass  # e.g. file locked because the browser is still running -- skip, not fatal


def ensure_browsers_exit_cleanly() -> None:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        return
    for relative_path in _BROWSER_PROFILE_PREFERENCES_PATHS:
        preferences_path = Path(local_app_data) / relative_path
        _mark_browser_profile_as_cleanly_exited(preferences_path)
        _disable_autofill_suggestions(preferences_path)


def ensure_target_prerequisites() -> str:
    """Runs all Target-PC prerequisite checks, auto-installing/fixing what it can.
    Returns the resolved WinAppDriver executable path (informational -- Session resolves
    its own path independently via factory.driver_factory). Raises RuntimeError if a step
    needed an admin approval that wasn't given.

    This is the one standalone pass/fail gate: if every step here passes, automation may
    proceed; if any step fails, it must not. It launches WinAppDriver exactly once, as a
    self-test (ensure_winappdriver_can_launch()), and closes it right back down -- it does
    not leave anything running for Session to reuse; Session launches its own, later and
    independently, via the same factory.driver_factory functions.
    """
    ensure_developer_mode()
    winappdriver_path = ensure_winappdriver_installed()
    ensure_winappdriver_can_launch()
    ensure_python_packages()
    ensure_browsers_exit_cleanly()
    print("PC checks OK.")
    return winappdriver_path
