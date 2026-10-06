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
"""

import time
from typing import Optional

import requests

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
