"""
Centralized runtime config for the Target PC automation -- WinAppDriver connection info,
app exe/process names, browser process names, mock-server default port, and the
WinAppDriver/Node.js install-path search lists. Values come from environment variables
(loaded from a .env file at the project root via python-dotenv, if present), falling back
to the exact defaults already confirmed working throughout Phase 0/2 if unset -- so an
absent .env changes nothing.

Before this module existed, these same values were hardcoded independently in multiple
places (factory/driver_factory.py AND factory/browser_driver_factory.py each defined their
own copy of WINAPPDRIVER_URL; factory/prerequisites.py had WINAPPDRIVER_HOST/PORT
separately again) -- already a real drift risk with zero actual drift yet, by luck. This
module is the one source of truth now; see PROJECT_PLAN.md Sec 3's "Deviation" note for
why this lives here rather than the originally-planned config/settings.py +
config/environments/*.env.example (a per-role MachineConfig dataclass).
"""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

WINAPPDRIVER_HOST = os.environ.get("DDA_WINAPPDRIVER_HOST", "127.0.0.1")
WINAPPDRIVER_PORT = int(os.environ.get("DDA_WINAPPDRIVER_PORT", "4723"))
WINAPPDRIVER_URL = f"http://{WINAPPDRIVER_HOST}:{WINAPPDRIVER_PORT}"

TARGET_EXE_NAME = os.environ.get("DDA_TARGET_EXE_NAME", "DellDataAssistant.TargetPc.exe")
TARGET_PROCESS_NAME = os.environ.get("DDA_TARGET_PROCESS_NAME", "DellDataAssistant.TargetPc")

MOCK_SERVER_DEFAULT_PORT = int(os.environ.get("DDA_MOCK_SERVER_PORT", "8443"))

BROWSER_PROCESS_NAMES = [
    name.strip()
    for name in os.environ.get("DDA_BROWSER_PROCESS_NAMES", "chrome,msedge").split(",")
    if name.strip()
]

# Confirmed window/tab title for the Dell sign-in page: "Sign In | Dell US" (see
# PROJECT_PLAN.md Sec 5.3c). All keywords here must appear in a window's title
# (case-insensitive) for it to be recognized as the sign-in page -- used as a fallback
# when the OS reuses an already-running browser window instead of opening a new one, so
# no new top-level window handle ever appears for the usual snapshot-diff check to find.
SIGN_IN_WINDOW_TITLE_KEYWORDS = [
    kw.strip().lower()
    for kw in os.environ.get("DDA_SIGN_IN_TITLE_KEYWORDS", "sign in,dell").split(",")
    if kw.strip()
]

WINAPPDRIVER_INSTALL_PATHS = [
    path.strip()
    for path in os.environ.get(
        "DDA_WINAPPDRIVER_INSTALL_PATHS",
        r"C:\Program Files (x86)\Windows Application Driver\WinAppDriver.exe;"
        r"C:\Program Files\Windows Application Driver\WinAppDriver.exe",
    ).split(";")
    if path.strip()
]

NODE_INSTALL_PATHS = [
    path.strip()
    for path in os.environ.get(
        "DDA_NODE_INSTALL_PATHS",
        r"C:\Program Files\nodejs\node.exe;C:\Program Files (x86)\nodejs\node.exe",
    ).split(";")
    if path.strip()
]
