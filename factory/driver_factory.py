"""
DriverFactory: idempotent WinAppDriver session registry, keyed by MachineRole.

Implements the launch-then-attach pattern and the legacy-capability-format workaround
confirmed necessary via the Phase 0 spike -- see PROJECT_PLAN.md Sec 4.2/4.3 and
tools/phase0_inspection_notes.md. Target-only for now (Source's launch flow is still
undetermined -- see PROJECT_PLAN.md Sec 10, open item 1).

Process/window inspection shells out to PowerShell rather than using psutil/pywin32
in-process. The in-process approach (psutil.process_iter + win32gui) was found to
intermittently crash the interpreter outright (exit code 15, no catchable exception, no
Windows crash/WER log entry, not reliably reproducible from one run to the next) when
combined with the network calls this module also makes. PowerShell subprocess calls
doing the equivalent process/window inspection never once failed across dozens of runs
during development -- see tools/phase0_inspection_notes.md. Slower per call, but reliable,
which matters more here.

(Later finding, also in tools/phase0_inspection_notes.md: most of that "exit code 15"
mystery was actually the app's own WebView2 renderer crashing ~47s after becoming
visible, not our code at all -- but the PowerShell-based approach here remains the more
robust choice regardless and was kept.)

Deliberately also does NOT use the Appium Python client's WebDriver class -- constructing
it and calling into it from this process hit the same unreliable-crash pattern.
`WinAppDriverSession`/`WinAppDriverElement` below are a minimal purpose-built wrapper
instead, exposing just what components/base_component.py needs (find_element(s), click,
send_keys, get_attribute, screenshot, page_source).
"""

import subprocess
import threading
import time
from enum import Enum
from typing import Optional

import requests

from factory import capabilities as caps
from factory.config import TARGET_EXE_NAME, TARGET_PROCESS_NAME, WINAPPDRIVER_URL
from factory.wait_utils import poll_until

LAUNCH_ATTEMPT_TIMEOUT = 35.0  # Confirmed necessary via testing: a short client timeout
                               # (previously tried: 5s) caused launches to silently fail
                               # to reach the app at all -- WinAppDriver appears to abort
                               # the server-side launch when the client disconnects early,
                               # contradicting the original assumption that disconnecting
                               # wouldn't affect server-side processing. Must stay connected
                               # for (approximately) WinAppDriver's own internal window-
                               # detection timeout. See tools/phase0_inspection_notes.md.
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


def _kill_existing_instances(exe_name: str) -> None:
    """Kills every process whose command line mentions exe_name -- not just the one with
    a visible window. Confirmed necessary: the app's single-instance lock silently
    swallows a new launch's CLI args if ANY matching instance (visible or hidden) is
    already running. See PROJECT_PLAN.md Sec 5.3a.
    """
    _run_powershell(
        f"Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -like '*{exe_name}*' "
        f"-or $_.Name -eq '{exe_name}' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId "
        f"-Force -ErrorAction SilentlyContinue }}",
        timeout=30,
    )
    time.sleep(1)


def _find_main_window_hwnd(process_name: str = TARGET_PROCESS_NAME) -> Optional[str]:
    output = _run_powershell(
        f"$p = Get-Process -Name '{process_name}' -ErrorAction SilentlyContinue | "
        "Where-Object { $_.MainWindowHandle -ne 0 } | Select-Object -First 1; "
        "if ($p) { '{0:X}' -f $p.MainWindowHandle.ToInt64() }"
    )
    return output or None


_MASK_CHARS = set("•*●○")


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
            # forced char-by-char typing below instead of one bulk /value call. Ctrl+A
            # then Backspace simulates genuine keyboard input instead, which the field's
            # own event handlers actually see.
            try:
                self._select_all_and_delete()
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

    _CONTROL_KEY = ""
    _BACKSPACE_KEY = ""

    def _select_all_and_delete(self) -> None:
        """Sends Ctrl+A then Backspace as real key events -- see send_keys()'s comment
        for why this replaces WinAppDriver's /clear endpoint. The value array
        [CONTROL, "a", CONTROL] is the standard WebDriver convention for "press Ctrl,
        send 'a' while held, release Ctrl" in one call; Backspace follows as its own
        call once the selection has actually taken effect.
        """
        self._session._post(f"/element/{self.id}/value", {"value": [self._CONTROL_KEY, "a", self._CONTROL_KEY]})
        time.sleep(0.1)
        self._session._post(f"/element/{self.id}/value", {"value": [self._BACKSPACE_KEY]})

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
        return self._session._get(f"/element/{self.id}/rect")


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


def _launch_then_attach(
    winappdriver_url: str, build_path: str, app_arguments: Optional[list[str]] = None
) -> WinAppDriverSession:
    _kill_existing_instances(TARGET_EXE_NAME)

    # Step 1: issue the launch. This reliably times out/errors even on a fully
    # successful launch (WinAppDriver's window-detection timeout is shorter than the
    # app's own render time) -- confirmed, see PROJECT_PLAN.md Sec 4.2.
    try:
        requests.post(
            f"{winappdriver_url}/session",
            json=caps.app_launch_capabilities(build_path, app_arguments),
            timeout=LAUNCH_ATTEMPT_TIMEOUT,
        )
    except requests.exceptions.RequestException:
        pass

    # Step 2: poll for the window.
    hwnd_hex = poll_until(
        _find_main_window_hwnd,
        timeout=WINDOW_POLL_TIMEOUT,
        interval=WINDOW_POLL_INTERVAL,
    )

    # Step 3: attach -- this is the real session.
    resp = requests.post(
        f"{winappdriver_url}/session",
        json=caps.app_attach_capabilities(hwnd_hex),
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return WinAppDriverSession(winappdriver_url, data["sessionId"])


class DriverFactory:
    _app_drivers: dict[MachineRole, WinAppDriverSession] = {}
    _lock = threading.RLock()

    @classmethod
    def get_app_driver(
        cls,
        role: MachineRole,
        build_path: Optional[str] = None,
        app_arguments: Optional[list[str]] = None,
    ) -> WinAppDriverSession:
        if role is MachineRole.SOURCE:
            raise NotImplementedError(
                "Source PC launch flow is not yet implemented -- blocked on Source PC "
                "build access. See PROJECT_PLAN.md Sec 10, open item 1."
            )
        with cls._lock:
            existing = cls._app_drivers.get(role)
            if existing is not None and _find_main_window_hwnd() is not None:
                return existing
            if build_path is None:
                raise ValueError("build_path is required to create a new session")
            driver = _launch_then_attach(WINAPPDRIVER_URL, build_path, app_arguments)
            cls._app_drivers[role] = driver
            return driver

    @classmethod
    def quit_all(cls) -> None:
        with cls._lock:
            for driver in cls._app_drivers.values():
                try:
                    driver.quit()
                except Exception:
                    pass
            cls._app_drivers.clear()

    @classmethod
    def kill_app(cls) -> None:
        """Force-kills any running instance of the Target PC app, regardless of session
        state. Safe to call unconditionally -- scoped by the app's own exe name, unlike a
        browser-process kill, which could take down unrelated windows (see
        flows/target/authentication/sign_in_flow.py's _cleanup_after_failure()). Used for
        failure cleanup: a single failed interaction shouldn't leave a half-finished app
        process for the next run to trip over. Also clears the idempotent driver
        registry, so the next get_app_driver() call launches fresh rather than returning
        a now-stale reference.
        """
        _kill_existing_instances(TARGET_EXE_NAME)
        with cls._lock:
            cls._app_drivers.clear()
