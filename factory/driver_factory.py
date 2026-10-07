"""
WinAppDriverSession/WinAppDriverElement: a minimal purpose-built WinAppDriver REST client,
exposing just what components/base_component.py needs (find_element(s), click, send_keys,
get_attribute, screenshot, page_source). Deliberately does NOT use the Appium Python
client's WebDriver class -- constructing it and calling into it from this process hit an
unreliable interpreter-crash pattern during Phase 0 (exit code 15, no catchable exception,
no Windows crash/WER log entry) -- see PROJECT_PLAN.md Sec 4.2 and
tools/phase0_inspection_notes.md.

Session lifecycle (launch-then-attach, idempotent registry, process/window inspection via
PowerShell) moved to factory/session.py's `Session` class -- this file is now just the
low-level REST client the Session (and everything built on it) uses underneath. See
factory/session.py's own docstring for why that consolidation happened (2026-10-06).

This module is also the sole owner of the actual WinAppDriver PROCESS's lifecycle --
finding it, checking if it's running, launching it elevated, killing it (ensure_
winappdriver_running()/kill_winappdriver() below) -- per explicit user direction
(2026-10-07): "the actual driver must be yielded by driver_factory." factory/session.py
calls into these rather than owning this logic itself. The standalone utils/
prerequisites.py gate (not part of this factory/ package) also calls these same two
functions for its own one-time launch-then-close self-test -- one source of truth either
way, not duplicated per caller.
"""

import socket
import subprocess
import time
import winreg
from pathlib import Path
from typing import Optional

import requests
from loguru import logger

from factory.config import WINAPPDRIVER_HOST, WINAPPDRIVER_INSTALL_PATHS, WINAPPDRIVER_PORT

_MASK_CHARS = set("•*●○")


def _run_powershell(command: str, timeout: int = 20) -> str:
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True, text=True, timeout=timeout,
    )
    return result.stdout.strip()


def find_winappdriver_path() -> Optional[str]:
    for path in WINAPPDRIVER_INSTALL_PATHS:
        if Path(path).exists():
            return path
    return None


def is_winappdriver_running() -> bool:
    try:
        with socket.create_connection((WINAPPDRIVER_HOST, WINAPPDRIVER_PORT), timeout=1.0):
            return True
    except OSError:
        return False


def _ensure_webview2_accessibility_env_var() -> None:
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


def ensure_winappdriver_running(startup_timeout: float = 90.0) -> None:
    """Starts WinAppDriver elevated. Idempotent: no-ops if something is already listening
    on the port. The one place that actually launches WinAppDriver for any caller --
    factory/session.py's Session (for a real automation run) and the standalone
    utils/prerequisites.py gate (for its own launch-then-close self-test) both call this
    same function rather than each owning their own copy.

    Confirmed via testing: a plain elevated `Start-Process -Verb RunAs` is sufficient to
    keep WinAppDriver alive (no stdin-redirection tricks needed, despite an earlier,
    apparently environment-dependent finding to the contrary -- see
    tools/phase0_inspection_notes.md for the full history). The WebView2 accessibility
    flag is supplied via a persisted User env var (_ensure_webview2_accessibility_env_var)
    rather than this process's own environment, since an elevated process does not
    inherit the launching process's in-memory environment.

    Caveat: if a WinAppDriver instance is already running (started by someone/something
    else), this cannot cheaply verify it is elevated -- only that the port is open. A
    non-elevated pre-existing instance will still fail to expose the WebView2 tree per
    PROJECT_PLAN.md Sec 5.1; if that happens, stop it and let this function start one
    properly.

    Bug fixed here, confirmed live (2026-10-07): Start-Process -Verb RunAs (without
    -Wait) returns almost immediately -- it requests the elevation and the UAC consent
    dialog appears asynchronously, it does not block until approved. A countdown that
    used to start right then, at 20s, meant a human taking more than ~20s to notice and
    click the prompt (easy in practice) caused this to raise before WinAppDriver was even
    granted elevation yet -- then re-running triggered a second, genuinely new elevation
    request, confusingly looking like "it's asking for UAC again" right after approving
    the first one. 90s matches how every other UAC-dependent wait in this codebase is
    already deliberately generous about human reaction time.
    """
    if is_winappdriver_running():
        return
    winappdriver_path = find_winappdriver_path()
    if not winappdriver_path:
        raise RuntimeError(
            "WinAppDriver is not installed at any known path -- run the prerequisites "
            "gate first to install it."
        )
    _ensure_webview2_accessibility_env_var()
    logger.info("WinAppDriver isn't running -- starting it elevated (this needs one admin approval)...")
    # -WindowStyle Hidden (2026-10-08): WinAppDriver.exe is a console app -- its console
    # window was visible on top of everything, including the Target app itself.
    # Confirmed live via a screenshot: WinAppDriver's own window (showing its verbose
    # request/response logging) sat directly over the Dell app, which matters because
    # the /screenshot endpoint captures whatever is actually on top/foreground, not
    # specifically our app's window (see factory/session.py's own comment on this same
    # "foreground capture" behavior). Hiding it doesn't change what WinAppDriver does --
    # it keeps logging to its own console buffer exactly as before, just not on screen.
    _run_powershell(f'Start-Process -FilePath "{winappdriver_path}" -Verb RunAs -WindowStyle Hidden')
    deadline = time.monotonic() + startup_timeout
    while time.monotonic() < deadline:
        if is_winappdriver_running():
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
    if not is_winappdriver_running():
        return True
    _run_powershell(
        "Start-Process powershell -Verb RunAs -ArgumentList "
        "'-NoProfile','-Command','Stop-Process -Name WinAppDriver -Force "
        "-ErrorAction SilentlyContinue' -Wait",
        timeout=60,
    )
    time.sleep(1.0)
    return not is_winappdriver_running()


def _text_matches(actual: Optional[str], expected: str) -> bool:
    """Exact match, except for masked password fields: confirmed via testing that a
    password input's /text correctly reads back as a repeated mask character (e.g.
    '••••••••'), never the plaintext -- comparing against the exact expected string would
    always (wrongly) fail there. If the entire actual string is one repeated mask
    character, compare lengths instead.
    """
    if actual == expected:
        return True
    if actual and len(set(actual)) == 1 and actual[0] in _MASK_CHARS:
        return len(actual) == len(expected)
    return False


class WinAppDriverElement:
    def __init__(self, session: "WinAppDriverSession", element_id: str):
        self._session = session
        self.id = element_id

    def click(self) -> None:
        self._session._post(f"/element/{self.id}/click", {})

    def click_at_center(self) -> None:
        """A real simulated mouse click at this element's center, instead of click()'s
        UIA Invoke-pattern /element/{id}/click. Confirmed live (2026-10-06): that
        Invoke call can return success (no exception, no error) for a WebView2/
        React-rendered icon button ("Migrate now") without the underlying onClick
        handler actually firing -- a known class of issue where the accessibility
        bridge's invoke action isn't wired to the real DOM click listener. Uses the
        classic two-step JSONWireProtocol sequence (moveto an element centers the
        mouse there with no offset given, then click() fires at wherever the mouse
        currently is) rather than the W3C Invoke pattern, which is the standard
        workaround for exactly this.
        """
        self._session._post("/moveto", {"element": self.id})
        self._session._post("/click", {"button": 0})

    def send_keys(self, text: str, verify: bool = True, max_attempts: int = 3) -> None:
        # Confirmed bug: sending the whole string in one /value call against a
        # React-controlled input (e.g. the sign-in email field) only sticks the LAST
        # character -- the component's re-render can't keep up with the whole batch
        # arriving at once. Click to focus, clear any existing content, then send one
        # character per request with a small delay so each keystroke is a discrete event
        # the component actually processes. Slower, but reliable -- see
        # tools/phase0_inspection_notes.md.
        #
        # Also confirmed: even this can still land incomplete/incorrect (e.g. a
        # transient dialog -- the Chrome "Restore pages?" crash-recovery prompt -- can
        # steal focus mid-sequence). WinAppDriver gave no error either time; the only way
        # to know is to read back what's actually there. So: type, then verify via
        # get_text() and retry the whole field (not just the missing tail, since we can't
        # tell which characters landed) up to max_attempts before giving up loudly.
        last_actual = None
        for attempt in range(max_attempts):
            self.click()
            time.sleep(0.2)

            # Confirmed need: a browser form field (e.g. the sign-in email field) can be
            # auto-filled by the browser itself (saved credentials/autofill) shortly
            # after focus -- asynchronously, not synchronously with our click. Clearing
            # immediately can race that: the field is still empty at clear-time, we type
            # our value, and the browser's autofill then overwrites/appends to it a
            # moment later. Wait for the field's own text to stop changing between reads
            # before clearing, so any autofill has already landed and we're clearing its
            # actual result, not racing it. Harmless on fields that never autofill (a
            # WPF/OTP field, or an empty field with nothing to fill): two consecutive
            # reads already match, so this returns immediately.
            self._wait_for_text_to_settle(timeout=1.0)

            # Bug fixed here, confirmed directly by the user (2026-10-06): WinAppDriver's
            # /clear endpoint was observed leaving stale text in place before new text was
            # typed -- it likely clears the underlying DOM value directly without firing
            # real key events, so a React-controlled input's own internal state can stay
            # out of sync with what /clear did, the same class of problem that already
            # forced char-by-char typing below instead of one bulk /value call.
            #
            # Bug fixed here AGAIN, confirmed via a live run the user watched directly
            # (2026-10-06): a held-Ctrl+A ("select all") combo, sent as the standard
            # WebDriver [CONTROL, "a", CONTROL] value array, visibly did not clear
            # browser-autofilled text either -- WinAppDriver is a generic UI-Automation-
            # based driver, not a browser-specific one (chromedriver/geckodriver), and
            # evidently doesn't translate that held-modifier convention into a real
            # Ctrl+A keystroke the way a browser-automation driver would. Replaced with a
            # modifier-free approach: move to the start of the field (Home), then send
            # Delete once per existing character -- only ever simple, unmodified
            # keypresses, which this driver clearly does deliver correctly (the
            # char-by-char typing below already relies on exactly that).
            try:
                self._clear_via_keys()
            except Exception:
                pass
            for ch in text:
                self._session._post(f"/element/{self.id}/value", {"value": [ch], "text": ch})
                time.sleep(0.05)
            if not verify:
                return
            time.sleep(0.2)
            last_actual = self.get_text()
            if _text_matches(last_actual, text):
                return
        raise RuntimeError(
            f"send_keys verification failed after {max_attempts} attempts: "
            f"expected {text!r}, field actually contains {last_actual!r}"
        )

    _HOME_KEY = ""
    _DELETE_KEY = ""

    def _clear_via_keys(self) -> None:
        """Clears the field using only simple, unmodified key events -- see
        send_keys()'s comment for why a held-Ctrl+A combo was replaced with this. Reads
        the field's current text to know how many characters are there, sends Home to
        put the cursor at the start regardless of where a prior click landed it, then
        sends Delete once per existing character to remove them all going forward. Each
        Delete is its own request/sleep, same deliberate pacing as the char-by-char
        typing below -- one discrete key event at a time is what this driver has been
        confirmed to actually deliver reliably.
        """
        try:
            current = self.get_text()
        except Exception:
            current = ""
        length = len(current) if current else 0
        if length == 0:
            return
        self._session._post(f"/element/{self.id}/value", {"value": [self._HOME_KEY]})
        time.sleep(0.05)
        for _ in range(length):
            self._session._post(f"/element/{self.id}/value", {"value": [self._DELETE_KEY]})
            time.sleep(0.05)

    def _wait_for_text_to_settle(self, timeout: float, poll_interval: float = 0.2) -> None:
        deadline = time.monotonic() + timeout
        try:
            previous = self.get_text()
        except Exception:
            return  # can't read it -- nothing to settle on, proceed as before
        while time.monotonic() < deadline:
            time.sleep(poll_interval)
            try:
                current = self.get_text()
            except Exception:
                return
            if current == previous:
                return
            previous = current

    def get_text(self) -> str:
        return self._session._get(f"/element/{self.id}/text")

    def get_attribute(self, name: str) -> Optional[str]:
        return self._session._get(f"/element/{self.id}/attribute/{name}")

    @property
    def rect(self) -> dict:
        # Confirmed live (2026-10-06), on multiple machines: WinAppDriver's combined
        # W3C /rect endpoint returns 501 Not Implemented for every element, every call,
        # on some installs -- but WinAppDriver is a JSONWireProtocol-era server, not a
        # pure W3C one, and the older separate /location and /size endpoints are a
        # distinct code path server-side that may still work where /rect doesn't. Try
        # /rect first (cheap, one call); only fall back to assembling the equivalent
        # from /location + /size on a 501, rather than always paying for two requests.
        try:
            return self._session._get(f"/element/{self.id}/rect")
        except requests.HTTPError as exc:
            if exc.response is None or exc.response.status_code != 501:
                raise
            location = self._session._get(f"/element/{self.id}/location")
            size = self._session._get(f"/element/{self.id}/size")
            return {
                "x": location["x"],
                "y": location["y"],
                "width": size["width"],
                "height": size["height"],
            }


class WinAppDriverSession:
    """Minimal WinAppDriver REST client -- just what components/flows need. See module
    docstring for why this exists instead of the Appium Python client's WebDriver.
    """

    def __init__(self, base_url: str, session_id: str):
        self.base_url = base_url
        self.session_id = session_id

    def _get(self, path: str):
        resp = requests.get(f"{self.base_url}/session/{self.session_id}{path}", timeout=30)
        resp.raise_for_status()
        return resp.json().get("value")

    def _post(self, path: str, body: dict):
        resp = requests.post(f"{self.base_url}/session/{self.session_id}{path}", json=body, timeout=30)
        resp.raise_for_status()
        return resp.json().get("value")

    @property
    def page_source(self) -> str:
        return self._get("/source")

    def find_element(self, by: str, value: str) -> WinAppDriverElement:
        result = self._post("/element", {"using": by, "value": value})
        element_id = result.get("ELEMENT") or result.get("element-6066-11e4-a52e-4f735466cecf")
        return WinAppDriverElement(self, element_id)

    def find_elements(self, by: str, value: str) -> list[WinAppDriverElement]:
        results = self._post("/elements", {"using": by, "value": value}) or []
        elements = []
        for r in results:
            element_id = r.get("ELEMENT") or r.get("element-6066-11e4-a52e-4f735466cecf")
            elements.append(WinAppDriverElement(self, element_id))
        return elements

    def get_screenshot_as_png(self) -> bytes:
        import base64
        return base64.b64decode(self._get("/screenshot"))

    def quit(self) -> None:
        requests.delete(f"{self.base_url}/session/{self.session_id}", timeout=30)
