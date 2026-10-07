"""
Session: owns the full lifecycle of one automation run against the Target PC app -- the
app process itself, its WinAppDriver attach, and (when opened) the external sign-in
browser's WinAppDriver attach. All three live and die together.

Consolidates the previously separate factory/driver_factory.py's DriverFactory class and
the now-removed factory/browser_driver_factory.py into one object, per explicit user
direction (2026-10-06): "remove the browser driver and use a single idempotent driver
which manages everything... it's basically a session: if a single step fails then
everything must be closed." close() tears down the browser window (if open), the app
process, and WinAppDriver itself, unconditionally -- call it on ANY interaction failure,
not just ones that look app-specific or browser-specific, since the three are managed as
one unit now.

Idempotent the same way DriverFactory was: get() reuses the existing Session for a role
if the app window is still alive, otherwise launches fresh. All process/window inspection
still shells out to PowerShell rather than using psutil/pywin32 in-process -- confirmed
necessary via Phase 0 (intermittent interpreter crashes, exit code 15/255, no catchable
exception, no WER log entry -- see PROJECT_PLAN.md Sec 4.2/5.3b/tools/phase0_inspection_notes.md).

This file's browser-window-finding logic (EnumWindows via an embedded C# snippet, title
matching as a fallback for the OS reusing an already-running browser window) is carried
over unchanged from the removed browser_driver_factory.py -- see its own comments inline
for why each piece is there; none of that was simplified or re-derived, just relocated.

Does not own the WinAppDriver PROCESS's own lifecycle (2026-10-07, per explicit user
direction: "the actual driver must be yielded by driver_factory"). factory/
driver_factory.py is the sole owner of finding/launching/killing WinAppDriver itself
(ensure_winappdriver_running()/kill_winappdriver(), imported below); this module just
calls into it at the right points (before launching/attaching the app, and during
close()). The standalone utils/prerequisites.py gate (not part of this factory/
package) calls the same two driver_factory functions for its own one-time
launch-then-close self-test -- one source of truth either way, not duplicated per caller.
"""

import subprocess
import tempfile
import threading
import time
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple

import requests
from loguru import logger

from components.base_component import BaseComponent
from factory import capabilities as caps
from factory.config import (
    BROWSER_PROCESS_NAMES,
    SIGN_IN_WINDOW_TITLE_KEYWORDS,
    SOURCE_EXE_NAME,
    SOURCE_PROCESS_NAME,
    TARGET_EXE_NAME,
    TARGET_PROCESS_NAME,
    WINAPPDRIVER_URL,
)
from factory.driver_factory import WinAppDriverSession, ensure_winappdriver_running, kill_winappdriver
from utils.wait_utils import poll_until

LAUNCH_ATTEMPT_TIMEOUT = 35.0  # Confirmed necessary via testing: a short client timeout
                               # (previously tried: 5s) caused launches to silently fail
                               # to reach the app at all -- WinAppDriver appears to abort
                               # the server-side launch when the client disconnects early.
                               # Must stay connected for (approximately) WinAppDriver's
                               # own internal window-detection timeout.
WINDOW_POLL_TIMEOUT = 40.0
WINDOW_POLL_INTERVAL = 0.5  # poll quickly -- the renderer has been observed to crash
                            # ~47s after becoming visible (see PROJECT_PLAN.md Sec 5.3b),
                            # so minimizing time-to-attach matters


class MachineRole(str, Enum):
    SOURCE = "source"
    TARGET = "target"


def _run_powershell(command: str, timeout: int = 20) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True, text=True, timeout=timeout,
    )
    return result.stdout.strip()


def _is_process_running(exe_name: str) -> bool:
    output = _run_powershell(
        "if (Get-CimInstance Win32_Process | Where-Object { "
        f"$_.CommandLine -like '*{exe_name}*' -or $_.Name -eq '{exe_name}' "
        "}) { 'yes' }"
    )
    return output == "yes"


def _kill_existing_instances(exe_name: str) -> None:
    """Kills every process whose command line mentions exe_name -- not just the one with
    a visible window. Confirmed necessary: the app's single-instance lock silently
    swallows a new launch's CLI args if ANY matching instance (visible or hidden) is
    already running. See PROJECT_PLAN.md Sec 5.3a.

    Bug fixed here, confirmed live (2026-10-07): the Dell app runs elevated (confirmed
    via Phase 0 -- it requires admin elevation), so a non-elevated Stop-Process call
    here was silently failing to actually kill it, every time, same UIPI mechanism
    documented on driver_factory.kill_winappdriver(). Now verifies the plain kill
    actually worked and retries elevated (one more admin prompt) if not, so
    error/interrupt cleanup is guaranteed rather than silently incomplete.
    """
    _run_powershell(
        f"Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -like '*{exe_name}*' "
        f"-or $_.Name -eq '{exe_name}' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId "
        f"-Force -ErrorAction SilentlyContinue }}",
        timeout=30,
    )
    time.sleep(1)
    if not _is_process_running(exe_name):
        return
    _run_powershell(
        "Start-Process powershell -Verb RunAs -ArgumentList "
        "'-NoProfile','-Command','Get-CimInstance Win32_Process | Where-Object { "
        f"$_.CommandLine -like \"*{exe_name}*\" -or $_.Name -eq \"{exe_name}\" }} "
        "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force "
        "-ErrorAction SilentlyContinue }' -Wait",
        timeout=60,
    )
    time.sleep(1)


def _find_main_window_hwnd(process_name: str = TARGET_PROCESS_NAME) -> Optional[str]:
    output = _run_powershell(
        f"$p = Get-Process -Name '{process_name}' -ErrorAction SilentlyContinue | "
        "Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1; "
        "if ($p) { '{0:X}' -f $p.MainWindowHandle.ToInt64() }"
    )
    return output or None


# Confirmed live (2026-10-06): WinAppDriver's /screenshot endpoint is a real screen
# capture, not scoped to the session's own app window -- if that window is occluded or
# not focused, the "screenshot" captures whatever IS actually visible/foreground instead
# (confirmed directly: it captured this very automation's own terminal/editor window's
# content, not the Dell app, during an unattended run). UI Automation reads (get_text(),
# .rect, etc.) are unaffected -- they read the accessibility tree regardless of on-screen
# visibility -- only the OCR-fallback screenshot path needs this. Same embedded-C#-via-
# PowerShell approach as _ENUM_WINDOWS_SCRIPT above, and for the same reason (confirmed
# working via -File; inline -Command with this much embedded C# has not been retested
# here and the existing script already solved the escaping problem).
_ACTIVATE_WINDOW_SCRIPT = '''param([string]$HwndHex)
$Hwnd = [IntPtr]::new([Convert]::ToInt64($HwndHex, 16))

Add-Type @'
using System;
using System.Runtime.InteropServices;

public class DdaWindowActivator {
    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
    [DllImport("user32.dll")]
    public static extern bool IsIconic(IntPtr hWnd);
}
'@ -ErrorAction SilentlyContinue

if ([DdaWindowActivator]::IsIconic($Hwnd)) {
    [DdaWindowActivator]::ShowWindow($Hwnd, 9) | Out-Null  # SW_RESTORE
}
[DdaWindowActivator]::SetForegroundWindow($Hwnd) | Out-Null
'''

_activate_window_script_path: Optional[Path] = None


def _get_activate_window_script_path() -> Path:
    global _activate_window_script_path
    if _activate_window_script_path is None:
        path = Path(tempfile.gettempdir()) / "dda_activate_window.ps1"
        path.write_text(_ACTIVATE_WINDOW_SCRIPT, encoding="utf-8")
        _activate_window_script_path = path
    return _activate_window_script_path


def bring_window_to_foreground(hwnd_hex: str) -> None:
    """Restores (if minimized) and foregrounds the given top-level window, so a
    subsequent get_screenshot_as_png() call actually captures it instead of whatever
    else is currently visible. See the module-level comment above this function for why
    this exists -- call it only right before an OCR-reliant screenshot, not before every
    interaction, since stealing focus is disruptive and UIA reads don't need it.
    """
    script_path = _get_activate_window_script_path()
    subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path), "-HwndHex", hwnd_hex],
        capture_output=True, text=True, timeout=10,
    )
    time.sleep(0.2)  # small settle delay for the activation/redraw to actually land


def is_uac_prompt_showing() -> bool:
    """Detects whether a Windows UAC elevation prompt is currently showing, WITHOUT
    touching the secure desktop the prompt itself runs on (which is categorically
    off-limits to UI Automation -- see PROJECT_PLAN.md Sec 10 item 11). `consent.exe` is
    the standard Windows process that hosts every UAC prompt: it exists for exactly as
    long as the prompt is on screen (spawned when the prompt appears, exits the instant
    the user clicks Yes/No or it's otherwise dismissed) and lives on the NORMAL desktop's
    process list -- observing its presence is an ordinary process check, not a breach of
    the secure-desktop boundary. Confirmed directly by the user (2026-10-06): UAC timing
    had become hard to reason about (the flow closes the sign-in browser before this
    resolves and waits on an indirect signal instead) -- this gives a direct, real signal
    for "is a human needed right now" instead of inferring it from a downstream screen.
    """
    return _run_powershell(
        "if (Get-Process -Name consent -ErrorAction SilentlyContinue) { 'yes' }"
    ) == "yes"


def _launch_then_attach(
    build_path: str,
    app_arguments: Optional[list] = None,
    exe_name: str = TARGET_EXE_NAME,
    process_name: str = TARGET_PROCESS_NAME,
) -> WinAppDriverSession:
    # Session ensures WinAppDriver is actually running before it ever tries to
    # launch/attach the app, via factory.driver_factory (see module docstring) -- not
    # dependent on the standalone prerequisites.ensure_prerequisites() gate
    # having been called first, even though role_runner.py happens to call that too for
    # the separate machine-level setup checks it covers.
    ensure_winappdriver_running()
    _kill_existing_instances(exe_name)

    # Step 1: issue the launch. This reliably times out/errors even on a fully
    # successful launch (WinAppDriver's window-detection timeout is shorter than the
    # app's own render time) -- confirmed, see PROJECT_PLAN.md Sec 4.2.
    try:
        requests.post(
            f"{WINAPPDRIVER_URL}/session",
            json=caps.app_launch_capabilities(build_path, app_arguments),
            timeout=LAUNCH_ATTEMPT_TIMEOUT,
        )
    except requests.exceptions.RequestException:
        pass

    # Step 2: poll for the window.
    hwnd_hex = poll_until(
        lambda: _find_main_window_hwnd(process_name), timeout=WINDOW_POLL_TIMEOUT, interval=WINDOW_POLL_INTERVAL,
    )

    # Step 3: attach -- this is the real session.
    resp = requests.post(f"{WINAPPDRIVER_URL}/session", json=caps.app_attach_capabilities(hwnd_hex), timeout=30)
    resp.raise_for_status()
    return WinAppDriverSession(WINAPPDRIVER_URL, resp.json()["sessionId"])


# ---------------------------------------------------------------------------
# Browser-window finding -- carried over unchanged from the removed
# factory/browser_driver_factory.py. See that history in this file's own
# module docstring; comments below are original, not re-derived.
# ---------------------------------------------------------------------------

# Confirmed via live testing (2026-10-05): enumerating browser windows MUST use real
# Win32 window enumeration (EnumWindows), NOT Get-Process's MainWindowHandle property --
# that property reports only ONE window per process object, and the OS routinely opens
# the sign-in window inside an ALREADY-RUNNING browser process (reusing it) rather than
# spawning a new one. The new window was consistently invisible to the old
# Get-Process-based check for exactly this reason -- not a timing issue, a structural
# one: no number of retries or longer timeouts would ever have found it.
#
# Written to a real .ps1 file and invoked via -File, not passed inline via -Command --
# confirmed via testing that embedding this C# in a double-quoted here-string
# (@" ... "@) passed as a -Command string breaks, since the C# source's own double
# quotes (e.g. "user32.dll") terminate the here-string early. A single-quoted
# here-string fixes that, but -File sidesteps the whole class of escaping problems and
# is what's actually verified working.
_ENUM_WINDOWS_SCRIPT = '''param([string]$NamesCsv)
$Names = $NamesCsv -split ','

Add-Type @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;

public class DdaWindowEnumerator {
    [DllImport("user32.dll")]
    private static extern bool EnumWindows(EnumWindowsProc enumProc, IntPtr lParam);
    [DllImport("user32.dll")]
    private static extern bool IsWindowVisible(IntPtr hWnd);
    [DllImport("user32.dll")]
    private static extern int GetWindowThreadProcessId(IntPtr hWnd, out int processId);
    [DllImport("user32.dll", CharSet = CharSet.Auto)]
    private static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    public static List<string> GetVisibleWindows() {
        var results = new List<string>();
        EnumWindowsProc callback = (hWnd, lParam) => {
            if (IsWindowVisible(hWnd)) {
                int pid;
                GetWindowThreadProcessId(hWnd, out pid);
                var sb = new StringBuilder(512);
                GetWindowText(hWnd, sb, sb.Capacity);
                results.Add(pid + ":" + hWnd.ToInt64().ToString("X") + ":" + sb.ToString());
            }
            return true;
        };
        EnumWindows(callback, IntPtr.Zero);
        return results;
    }
}
'@ -ErrorAction SilentlyContinue

$ids = (Get-Process -Name $Names -ErrorAction SilentlyContinue).Id
[DdaWindowEnumerator]::GetVisibleWindows() | ForEach-Object {
    $parts = $_ -split ':', 3
    if ($ids -contains [int]$parts[0]) { $_ }
}
'''

_enum_windows_script_path: Optional[Path] = None


def _get_enum_windows_script_path() -> Path:
    global _enum_windows_script_path
    if _enum_windows_script_path is None:
        path = Path(tempfile.gettempdir()) / "dda_list_browser_windows.ps1"
        path.write_text(_ENUM_WINDOWS_SCRIPT, encoding="utf-8")
        _enum_windows_script_path = path
    return _enum_windows_script_path


def list_browser_windows_with_titles() -> List[Tuple[str, str]]:
    """Every currently-open top-level window (hwnd_hex, title) pair across all supported
    browser processes, regardless of which one opened it or what it shows.
    """
    script_path = _get_enum_windows_script_path()
    names_csv = ",".join(BROWSER_PROCESS_NAMES)
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path), "-NamesCsv", names_csv],
        capture_output=True, text=True, timeout=20,
    )
    windows = []
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(":", 2)
        if len(parts) >= 2:
            windows.append((parts[1], parts[2] if len(parts) > 2 else ""))
    return windows


def list_browser_window_hwnds() -> set:
    """Snapshot of every currently-open top-level window handle (hex) across all
    supported browser processes. Call this BEFORE triggering an action expected to open
    a new browser window, so the new window can be told apart from ones already open.
    """
    return {hwnd for hwnd, _ in list_browser_windows_with_titles()}


def _title_matches_sign_in_page(title: str) -> bool:
    lowered = title.lower()
    return all(keyword in lowered for keyword in SIGN_IN_WINDOW_TITLE_KEYWORDS)


def find_new_browser_window_hwnd(known_hwnds: set) -> Optional[str]:
    """Returns the hex hwnd of the sign-in browser window, or None if it hasn't shown up
    yet. Prefers a window not present in known_hwnds (the common case: a genuinely new
    top-level window). Falls back to matching by window/tab title (confirmed "Sign In |
    Dell US", see SIGN_IN_WINDOW_TITLE_KEYWORDS) across ALL currently open browser
    windows -- confirmed via live testing (2026-10-06) that the OS sometimes reuses an
    already-running browser window (opens a new tab in it) instead of spawning a new one,
    in which case no hwnd is ever "new" even though the real sign-in page is genuinely
    showing.
    """
    windows = list_browser_windows_with_titles()
    new_hwnds = [hwnd for hwnd, _ in windows if hwnd not in known_hwnds]
    if new_hwnds:
        return new_hwnds[0]
    for hwnd, title in windows:
        if _title_matches_sign_in_page(title):
            return hwnd
    return None


def _attach_to_browser_window(hwnd_hex: str) -> WinAppDriverSession:
    resp = requests.post(
        f"{WINAPPDRIVER_URL}/session",
        json={"desiredCapabilities": {"appTopLevelWindow": hwnd_hex, "platformName": "Windows", "deviceName": "WindowsPC"}},
        timeout=20,
    )
    resp.raise_for_status()
    return WinAppDriverSession(WINAPPDRIVER_URL, resp.json()["sessionId"])


def _close_browser_window(session: WinAppDriverSession) -> None:
    # Closes via the window's own caption-bar Close button, not a process-level kill --
    # this is the user's real everyday browser profile, which routinely has other
    # unrelated windows open in the same process.
    close_button = BaseComponent(session, "xpath", '//*[@Name="Close"]', "BrowserWindowCloseButton", timeout=3.0)
    if close_button.exists(timeout=3.0):
        close_button.click()


class Session:
    """One Session per role, idempotent (Session.get() reuses a live one). Owns:
      - self.app: the Target PC app's WinAppDriverSession.
      - self.browser: the external sign-in browser's WinAppDriverSession, set only while
        one is attached (see attach_browser()/close_browser()).
    close() tears down both together plus WinAppDriver itself -- the all-or-nothing unit
    the user asked for. Also usable as a context manager: `with Session.get(...) as s:`
    closes everything if the body raises, same as calling close() in an except block.
    """

    _instances: dict = {}
    _lock = threading.RLock()

    def __init__(self):
        self.app: Optional[WinAppDriverSession] = None
        self.browser: Optional[WinAppDriverSession] = None
        self._exe_name: str = TARGET_EXE_NAME

    @classmethod
    def get(
        cls,
        role: MachineRole = MachineRole.TARGET,
        build_path: Optional[str] = None,
        app_arguments: Optional[list] = None,
    ) -> "Session":
        exe_name, process_name = (
            (SOURCE_EXE_NAME, SOURCE_PROCESS_NAME) if role is MachineRole.SOURCE
            else (TARGET_EXE_NAME, TARGET_PROCESS_NAME)
        )
        with cls._lock:
            existing = cls._instances.get(role)
            if existing is not None and existing.app is not None and _find_main_window_hwnd(process_name) is not None:
                return existing
            if build_path is None:
                raise ValueError("build_path is required to create a new session")
            session = cls()
            session._exe_name = exe_name
            session.app = _launch_then_attach(build_path, app_arguments, exe_name=exe_name, process_name=process_name)
            cls._instances[role] = session
            return session

    def snapshot_browser_windows(self) -> set:
        """Call BEFORE an action expected to open the sign-in browser, so attach_browser()
        can tell the new window apart from ones already open."""
        return list_browser_window_hwnds()

    def attach_browser(self, known_hwnds: set, timeout: float = 20.0) -> WinAppDriverSession:
        hwnd_hex = poll_until(lambda: find_new_browser_window_hwnd(known_hwnds), timeout=timeout, interval=0.5)
        self.browser = _attach_to_browser_window(hwnd_hex)
        return self.browser

    def close_browser(self) -> None:
        if self.browser is None:
            return
        try:
            _close_browser_window(self.browser)
        except Exception:
            pass
        try:
            self.browser.quit()
        except Exception:
            pass
        self.browser = None

    def close(self) -> None:
        """Tears down everything together -- browser window, app process, WinAppDriver
        itself -- per explicit user direction (2026-10-06): "if any interaction is
        failed Desktop, default browser and driver must exit all together... if a
        single step fails then everything must be closed." Idempotent: safe to call even
        if some/all of these are already gone (e.g. the app crashed on its own first).

        Bug fixed here, confirmed live (2026-10-07): these three steps used to run
        unprotected, one after another -- confirmed via a live traceback that a second
        KeyboardInterrupt (the user pressing Ctrl+C again, e.g. right after seeing an
        earlier crash/error) landing mid-cleanup (inside _kill_existing_instances()'s
        own time.sleep()) aborted close() entirely before kill_winappdriver() was ever
        reached, leaving WinAppDriver running despite the user explicitly interrupting.
        Each step now runs independently, catching BaseException (so a repeat
        KeyboardInterrupt during cleanup doesn't skip the remaining steps) and logging
        a warning rather than aborting -- all three are always attempted. If any step
        was interrupted, KeyboardInterrupt is re-raised once at the end, after every
        cleanup step has had its chance, so Ctrl+C still ultimately stops the program.
        """
        interrupted = False
        for step_name, step in (
            ("close_browser", self.close_browser),
            ("_kill_existing_instances", lambda: _kill_existing_instances(self._exe_name)),
            ("kill_winappdriver", kill_winappdriver),
        ):
            try:
                step()
            except KeyboardInterrupt:
                interrupted = True
                logger.warning(
                    f"Session.close(): {step_name} was interrupted (Ctrl+C) -- "
                    "continuing with the remaining cleanup steps anyway"
                )
            except Exception as exc:
                logger.warning(
                    f"Session.close(): {step_name} failed ({exc}) -- continuing with "
                    "the remaining cleanup steps anyway"
                )
        self.app = None
        with self._lock:
            for role, sess in list(self._instances.items()):
                if sess is self:
                    del self._instances[role]
        if interrupted:
            raise KeyboardInterrupt

    def __enter__(self) -> "Session":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None:
            self.close()
        return None
