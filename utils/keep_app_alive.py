"""
Watches for the Target PC app + WinAppDriver dying (confirmed recurring in this
environment -- see PROJECT_PLAN.md Sec 4.2/5.3b/10: the WebView2 renderer reliably
crashes ~47s after becoming visible and appears to take WinAppDriver down with it, no
event-log trace either time) and relaunches both the moment either one goes down, using
the same restart-WinAppDriver -> launch -> attach-immediately sequence that has reliably
recovered it by hand throughout this session.

Usage:
    python utils/keep_app_alive.py --build-path PATH [--secret my-secret-active]
        [--mock-server-package PATH] [--poll-interval 3]

Runs until Ctrl+C. Prints one line per relaunch cycle with a timestamp and the new
session id, so you can see recovery happening instead of needing to ask for it.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from factory import capabilities as caps
from factory.config import TARGET_PROCESS_NAME, WINAPPDRIVER_URL
from utils.prerequisites import ensure_prerequisites
from factory.session import _find_main_window_hwnd
import requests


def P(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def is_app_alive() -> bool:
    return _find_main_window_hwnd(TARGET_PROCESS_NAME) is not None


def is_winappdriver_alive() -> bool:
    try:
        requests.get(f"{WINAPPDRIVER_URL}/status", timeout=2)
        return True
    except requests.exceptions.RequestException:
        return False


def relaunch(build_path: str, app_arguments: list[str]) -> str:
    P("relaunching: ensuring prerequisites (restarts WinAppDriver if needed)")
    ensure_prerequisites()

    P(f"relaunching: starting app with args {app_arguments}")
    subprocess.Popen(
        ["powershell", "-NoProfile", "-Command",
         f'Start-Process -FilePath "{build_path}" -ArgumentList '
         f'"{app_arguments[0]}","{app_arguments[1]}","{app_arguments[2]}" -Verb RunAs'],
    )
    time.sleep(2)

    hwnd_hex = _find_main_window_hwnd(TARGET_PROCESS_NAME)
    if not hwnd_hex:
        raise RuntimeError("relaunch: app window never appeared")

    resp = requests.post(f"{WINAPPDRIVER_URL}/session", json=caps.app_attach_capabilities(hwnd_hex), timeout=30)
    resp.raise_for_status()
    session_id = resp.json()["sessionId"]
    P(f"relaunched and attached: session_id={session_id}")
    return session_id


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--build-path", required=True)
parser.add_argument("--secret", default="my-secret-active")
parser.add_argument("--cert-path", required=True, help="Path to the GlassFloor test harness cert.pfx -- no default, machine-specific")
parser.add_argument("--server-address", default="127.0.0.1:8443")
parser.add_argument("--poll-interval", type=float, default=3.0)
args = parser.parse_args()

app_arguments = [args.secret, args.cert_path, args.server_address]

P("keep_app_alive: starting watch loop (Ctrl+C to stop)")
relaunch(args.build_path, app_arguments)

while True:
    time.sleep(args.poll_interval)
    if not is_app_alive() or not is_winappdriver_alive():
        P("detected app or WinAppDriver down -- recovering")
        try:
            relaunch(args.build_path, app_arguments)
        except Exception as exc:
            P(f"relaunch attempt failed, will retry next poll: {exc}")
