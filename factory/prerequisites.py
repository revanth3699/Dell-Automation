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
    """Best-effort stop of any running WinAppDriver instance. Returns whether it is
    confirmed stopped afterward (port no longer open) -- checked rather than assumed.

    Caveat, confirmed by the same UIPI mechanism noted in ensure_winappdriver_running()
    and PROJECT_PLAN.md Sec 5.1: WinAppDriver normally runs elevated (started via
    Start-Process -Verb RunAs), and a non-elevated process cannot terminate a
    higher-integrity one. If the caller isn't itself elevated, the Stop-Process call
    below will silently fail to actually kill it -- that's why this re-tests the port
    afterward instead of trusting the command's own exit status.
    """
    _run_powershell("Stop-Process -Name WinAppDriver -Force -ErrorAction SilentlyContinue")
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


def ensure_target_prerequisites() -> str:
    """Runs all Target-PC prerequisite checks, auto-installing/fixing what it can.
    Returns the resolved WinAppDriver executable path. Raises RuntimeError if a step
    needed an admin approval that wasn't given.
    """
    ensure_developer_mode()
    winappdriver_path = ensure_winappdriver_installed()
    ensure_winappdriver_running(winappdriver_path)
    ensure_python_packages()
    print("All Target PC prerequisites OK.")
    return winappdriver_path
