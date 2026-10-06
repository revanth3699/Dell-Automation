"""
Prerequisite checks + auto-install for running WinAppDriver-based automation against the
Target PC app. Target-only (see PROJECT_PLAN.md Sec 10 open item: Source's launch flow is
still undetermined, pending Source PC build access).

Covers, in order: Windows Developer Mode, WinAppDriver installed, WinAppDriver running
elevated (required -- the app itself needs admin elevation, confirmed via Phase 0 spike,
see PROJECT_PLAN.md Sec 5.1), and the required Python packages. Node.js (for the
GlassFloor mock server, Sec 5.3a) is checked separately via ensure_mock_server_prerequisites
since it's only needed for that launch mode.
"""

import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import winreg
from pathlib import Path

from factory.config import NODE_INSTALL_PATHS, WINAPPDRIVER_HOST, WINAPPDRIVER_INSTALL_PATHS, WINAPPDRIVER_PORT

REQUIRED_PACKAGES = {
    "selenium": "selenium",
    "requests": "requests",
}

def _run_powershell(command: str, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True, text=True, timeout=timeout,
    )


def _port_is_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


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


def find_winappdriver() -> str | None:
    for path in WINAPPDRIVER_INSTALL_PATHS:
        if Path(path).exists():
            return path
    return None


def ensure_winappdriver_installed() -> str:
    path = find_winappdriver()
    if path:
        return path
    print("WinAppDriver not found -- installing via winget (this needs one admin approval)...")
    subprocess.run(
        ["winget", "install", "--id", "Microsoft.WindowsApplicationDriver",
         "--source", "winget", "--accept-source-agreements", "--accept-package-agreements", "--silent"],
        timeout=300,
    )
    path = find_winappdriver()
    if not path:
        raise RuntimeError("WinAppDriver install did not complete -- was the admin prompt approved?")
    return path


def check_winappdriver_running() -> bool:
    return _port_is_open(WINAPPDRIVER_HOST, WINAPPDRIVER_PORT)


def ensure_webview2_accessibility_env_var() -> None:
    """Persists WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS=--force-renderer-accessibility as a
    User-scope environment variable (not just this process's). Confirmed via testing that
    this is read correctly by a WinAppDriver instance launched via plain elevated
    Start-Process -Verb RunAs -- persisted env vars are read fresh from the registry at
    process creation regardless of elevation, so this works even though an elevated
    ("runas") process does not inherit the launching process's in-memory environment.
    Idempotent -- a no-op if already set correctly.
    """
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS")
        if value == "--force-renderer-accessibility":
            return
    except (FileNotFoundError, OSError):
        pass
    _run_powershell(
        '[System.Environment]::SetEnvironmentVariable('
        '"WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "--force-renderer-accessibility", "User")'
    )


def ensure_winappdriver_running(winappdriver_path: str, startup_timeout: float = 20.0) -> None:
    """Starts WinAppDriver elevated. Idempotent: no-ops if something is already listening
    on the port.

    Confirmed via testing: a plain elevated `Start-Process -Verb RunAs` is sufficient to
    keep WinAppDriver alive (no stdin-redirection tricks needed, despite an earlier,
    apparently environment-dependent finding to the contrary -- see
    tools/phase0_inspection_notes.md for the full history). The WebView2 accessibility
    flag is supplied via a persisted User env var (ensure_webview2_accessibility_env_var)
    rather than this process's own environment, since an elevated process does not
    inherit the launching process's in-memory environment.

    Caveat: if a WinAppDriver instance is already running (started by someone/something
    else), this cannot cheaply verify it is elevated -- only that the port is open. A
    non-elevated pre-existing instance will still fail to expose the WebView2 tree per
    Sec 5.1; if that happens, stop it and let this function start one properly.
    """
    if check_winappdriver_running():
        return
    ensure_webview2_accessibility_env_var()
    print("WinAppDriver isn't running -- starting it elevated (this needs one admin approval)...")
    _run_powershell(f'Start-Process -FilePath "{winappdriver_path}" -Verb RunAs')
    deadline = time.monotonic() + startup_timeout
    while time.monotonic() < deadline:
        if check_winappdriver_running():
            return
        time.sleep(0.5)
    raise RuntimeError(
        "WinAppDriver did not start within the timeout -- was the admin prompt approved?"
    )


def kill_winappdriver() -> bool:
    """Stops any running WinAppDriver instance. Returns whether it is confirmed stopped
    afterward (port no longer open) -- checked rather than assumed.

    Bug fixed here, confirmed live (2026-10-07): WinAppDriver normally runs elevated
    (started via Start-Process -Verb RunAs), and a non-elevated process cannot
    terminate a higher-integrity one (the same UIPI mechanism noted in
    ensure_winappdriver_running() and PROJECT_PLAN.md Sec 5.1) -- confirmed directly:
    a plain non-elevated kill attempt during this same project silently did nothing,
    every time, for exactly this reason. This used to just re-test the port and report
    failure; now it retries via an elevated Stop-Process (one more admin prompt, same
    mechanism already used to start WinAppDriver elevated in the first place) when the
    plain attempt didn't actually work, so cleanup on error/interrupt is guaranteed
    rather than silently incomplete.
    """
    _run_powershell("Stop-Process -Name WinAppDriver -Force -ErrorAction SilentlyContinue")
    time.sleep(1.0)
    if not check_winappdriver_running():
        return True
    _run_powershell(
        "Start-Process powershell -Verb RunAs -ArgumentList "
        "'-NoProfile','-Command','Stop-Process -Name WinAppDriver -Force "
        "-ErrorAction SilentlyContinue' -Wait",
        timeout=60,
    )
    time.sleep(1.0)
    return not check_winappdriver_running()


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
    Returns the resolved WinAppDriver executable path. Raises RuntimeError if a step
    needed an admin approval that wasn't given.
    """
    ensure_developer_mode()
    winappdriver_path = ensure_winappdriver_installed()
    ensure_winappdriver_running(winappdriver_path)
    ensure_python_packages()
    ensure_browsers_exit_cleanly()
    print("PC checks OK.")
    return winappdriver_path
