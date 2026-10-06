"""
Attaches a WinAppDriver session to the externally-opened sign-in browser's top-level
window (Chrome or Edge, whichever the OS default browser opened -- see
PROJECT_PLAN.md Sec 5.3c for why WinAppDriver-attach is used here instead of
Selenium/CDP: Chrome's own UIA/accessibility tree is queryable this way with zero extra
setup, and CDP requires a --remote-debugging-port that can't be retrofitted onto a
browser this process didn't launch itself).

Target-PC-only in practice: Source PC has no authentication step, so nothing on the
Source side ever opens an external sign-in browser for this module to attach to.

Confirmed via a live run (2026-10-05): the OS default browser is the user's everyday
browser, not a disposable test instance -- it is routinely already running with many
unrelated windows/tabs open. The original "grab the first window with a visible handle"
approach attached to the WRONG window in exactly that situation, which silently made
every downstream presence check (email/password/OTP fields) report "not found" even
though the real sign-in page was sitting in a different window the whole time. Fixed by
snapshotting the set of already-open browser windows before clicking Sign In, then
attaching only to a window that is genuinely new.

Confirmed via a live run (2026-10-06): the "genuinely new window" assumption itself isn't
always true -- the OS sometimes opens the Dell sign-in page as a new TAB inside an
ALREADY-RUNNING browser window instead of spawning a new top-level window. No hwnd is
ever "new" in that case (automation saw the email field as prefilled by the browser's own
autofill but never typed into it), so the snapshot-diff check alone waited out its full
timeout and incorrectly concluded no browser had opened. Fixed by also matching on the
window/tab's own title -- confirmed title "Sign In | Dell US" (see PROJECT_PLAN.md Sec
5.3c) -- across ALL currently open browser windows, not just new ones, as a fallback
alongside (not instead of) the new-hwnd check.
"""

import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

import requests

from components.base_component import BaseComponent
from factory.config import BROWSER_PROCESS_NAMES, SIGN_IN_WINDOW_TITLE_KEYWORDS, WINAPPDRIVER_URL
from factory.driver_factory import WinAppDriverSession
from factory.wait_utils import poll_until


def _run_powershell(command: str, timeout: int = 20) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True, text=True, timeout=timeout,
    )
    return result.stdout.strip()


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
    supported browser processes, regardless of which one opened it or what it shows.
    Call this BEFORE triggering a sign-in (or any) action that is expected to open a new
    browser window, so the new window can be told apart from ones already open.
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
    showing. Picks arbitrarily if somehow more than one candidate matches at once -- not
    expected in practice (one sign-in click opens exactly one window/tab).
    """
    windows = list_browser_windows_with_titles()
    new_hwnds = [hwnd for hwnd, _ in windows if hwnd not in known_hwnds]
    if new_hwnds:
        return new_hwnds[0]
    for hwnd, title in windows:
        if _title_matches_sign_in_page(title):
            return hwnd
    return None


def attach_to_browser_window(hwnd_hex: str) -> WinAppDriverSession:
    resp = requests.post(
        f"{WINAPPDRIVER_URL}/session",
        json={"desiredCapabilities": {"appTopLevelWindow": hwnd_hex, "platformName": "Windows", "deviceName": "WindowsPC"}},
        timeout=20,
    )
    resp.raise_for_status()
    return WinAppDriverSession(WINAPPDRIVER_URL, resp.json()["sessionId"])


def attach_to_new_sign_in_browser(known_hwnds: set, timeout: float = 20.0) -> WinAppDriverSession:
    """Waits for a browser window that wasn't in known_hwnds, then attaches to exactly
    that one. known_hwnds must be captured via list_browser_window_hwnds() BEFORE the
    action that opens the sign-in browser (e.g. clicking the app's Sign In button).
    """
    hwnd_hex = poll_until(
        lambda: find_new_browser_window_hwnd(known_hwnds),
        timeout=timeout, interval=0.5,
    )
    return attach_to_browser_window(hwnd_hex)


def _close_browser_window(session: WinAppDriverSession) -> None:
    # Closes via the window's own caption-bar Close button, not a process-level kill --
    # this is the user's real everyday browser profile, which routinely has other
    # unrelated windows open in the same process (see module docstring).
    close_button = BaseComponent(
        session, "xpath", '//*[@Name="Close"]', "BrowserWindowCloseButton", timeout=3.0,
    )
    if close_button.exists(timeout=3.0):
        close_button.click()


@contextmanager
def browser_driver(known_hwnds: set, timeout: float = 20.0) -> Iterator[WinAppDriverSession]:
    """Attaches to the next new sign-in browser window (see attach_to_new_sign_in_browser)
    and yields its WinAppDriverSession. On exit -- whether the body completes normally or
    raises -- closes that window via its own Close button and quits the WinAppDriver
    session, so callers don't need to track/close the browser session themselves.
    """
    session = attach_to_new_sign_in_browser(known_hwnds, timeout=timeout)
    try:
        yield session
    finally:
        try:
            _close_browser_window(session)
        except Exception:
            pass
        try:
            session.quit()
        except Exception:
            pass
