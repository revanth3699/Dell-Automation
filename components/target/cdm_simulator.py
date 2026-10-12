"""CdmSimulatorWindow: automates the CDM Simulator WPF app ("CDMSimulatorUI"), which
mimics Dell SupportAssist's role in launching the Target PC UI app and auto-answering
its backend Init/Job/Migration/Completed protocol messages -- used in place of real
SupportAssist integration, which isn't built yet. Confirmed from a user-supplied
screenshot (2026-10-12): paste the Target PC UI exe path into the "Exe:" textbox,
confirm "Auto-respond" is checked, click "Launch" -- the simulator then launches the
Target PC UI app itself and keeps auto-answering its backend messages for the rest of
the run. No further interaction with the simulator is needed afterward (see
factory/session.py's _launch_via_simulator_then_attach(), the only caller of this
class).
"""

from loguru import logger

from components.base_component import BaseComponent, ComponentActionError
from utils.wait_utils import poll_until
from locators.target.cdm_simulator import AUTO_RESPOND_CHECKBOX_LOCATOR, LAUNCH_BUTTON_LOCATOR


class CdmSimulatorWindow:
    def __init__(self, app_session):
        self._session = app_session
        self._launch_button = BaseComponent(app_session, *LAUNCH_BUTTON_LOCATOR, "CdmSimulatorLaunchButton")
        self._auto_respond_checkbox = BaseComponent(
            app_session, *AUTO_RESPOND_CHECKBOX_LOCATOR, "CdmSimulatorAutoRespondCheckbox"
        )

    def _find_exe_textbox(self, timeout: float = 10.0):
        """The "Exe:" textbox has no confirmed accessible Name -- found positionally
        (the first Edit control in the window), same convention already used by
        PairingCodeEntryScreen.enter_code() for its own unconfirmed WPF textboxes."""
        def _find():
            boxes = self._session.find_elements("xpath", "//Edit")
            return boxes[0] if boxes else None

        box = poll_until(_find, timeout=timeout, interval=0.5)
        if box is None:
            raise ComponentActionError('CdmSimulatorWindow: could not find the "Exe:" textbox')
        return box

    def set_target_exe_path(self, exe_path: str) -> None:
        """Types the Target PC UI exe path into the "Exe:" textbox. Uses the raw
        element's own send_keys() (clicks to focus, clears, types char-by-char with
        verification -- see WinAppDriverElement.send_keys()) rather than
        BaseComponent.type_text(), since the box is found positionally, not via a
        BaseComponent-wrapped locator (same reasoning as
        PairingCodeEntryScreen.enter_code())."""
        box = self._find_exe_textbox()
        box.send_keys(exe_path)

    def ensure_auto_respond_enabled(self, timeout: float = 5.0) -> None:
        """Confirmed via the user-supplied screenshot: Auto-respond defaults to
        checked. Reads the real current state via UI Automation's standard Toggle
        pattern (WinAppDriver attribute "Toggle.ToggleState": "0"=off, "1"=on,
        "2"=indeterminate) and only clicks if it's confirmed off -- never clicks
        blindly, since doing so on an already-checked box would UNCHECK it instead. If
        the state can't be read for any reason (this attribute name isn't independently
        confirmed live against this specific app), logs a warning and leaves the
        checkbox untouched rather than risk flipping it the wrong way."""
        try:
            element = self._session.find_element(*AUTO_RESPOND_CHECKBOX_LOCATOR)
            state = element.get_attribute("Toggle.ToggleState")
        except Exception as exc:
            logger.warning(
                f"CdmSimulatorWindow: could not read Auto-respond's toggle state ({exc}) "
                "-- leaving it untouched; confirm it's checked manually if this is a "
                "fresh simulator launch"
            )
            return
        if state == "0":
            logger.info("CdmSimulatorWindow: Auto-respond was off -- clicking to enable it")
            self._auto_respond_checkbox.click()
        elif state not in ("1", "2"):
            logger.warning(
                f"CdmSimulatorWindow: Auto-respond's toggle state was {state!r} "
                "(expected '0'/'1'/'2') -- leaving it untouched"
            )

    def launch(self) -> None:
        self._launch_button.click()
