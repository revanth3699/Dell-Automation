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

Confirmed live end-to-end (2026-10-12): typing the exe path, reading Auto-respond's
toggle state, and clicking Launch all work exactly as implemented here, and clicking
Launch genuinely brings up the Target PC UI app's own window.
"""

from loguru import logger

from components.base_component import BaseComponent
from locators.target.cdm_simulator import (
    AUTO_RESPOND_CHECKBOX_LOCATOR,
    EXE_TEXTBOX_LOCATOR,
    LAUNCH_BUTTON_LOCATOR,
)


class CdmSimulatorWindow:
    def __init__(self, app_session):
        self._exe_textbox = BaseComponent(app_session, *EXE_TEXTBOX_LOCATOR, "CdmSimulatorExeTextbox")
        self._launch_button = BaseComponent(app_session, *LAUNCH_BUTTON_LOCATOR, "CdmSimulatorLaunchButton")
        self._auto_respond_checkbox = BaseComponent(
            app_session, *AUTO_RESPOND_CHECKBOX_LOCATOR, "CdmSimulatorAutoRespondCheckbox"
        )

    def set_target_exe_path(self, exe_path: str) -> None:
        self._exe_textbox.type_text(exe_path)

    def ensure_auto_respond_enabled(self, timeout: float = 5.0) -> None:
        """Confirmed via the user-supplied screenshot AND a live read (2026-10-12):
        Auto-respond defaults to checked (Toggle.ToggleState="1"). Reads the real
        current state via UI Automation's standard Toggle pattern and only clicks if
        it's confirmed off ("0") -- never clicks blindly, since doing so on an
        already-checked box would UNCHECK it instead. If the state can't be read for
        any reason, logs a warning and leaves the checkbox untouched rather than risk
        flipping it the wrong way."""
        try:
            element = self._auto_respond_checkbox._find()
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
