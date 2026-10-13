"""Source PC's "Your battery is critically low." dialog -- "You'll need to plug this
PC into AC power to continue." Confirmed from a user-supplied screenshot (2026-10-14).
Distinct from Target's PlugIntoAcPowerDialog (a low-battery warning, waited out before
clicking Cancel) -- this one reports the battery as already critically low, not just a
warning, so per explicit user direction it's dismissed immediately, no wait first. See
assertions/source/battery_critically_low_dialog.py's is_showing().
"""

from components.base_component import BaseComponent
from locators.source.battery_critically_low_dialog import CANCEL_BUTTON_LOCATOR


class BatteryCriticallyLowDialog:
    def __init__(self, app_session):
        self._cancel_button = BaseComponent(app_session, *CANCEL_BUTTON_LOCATOR, "BatteryCriticallyLowCancelButton")

    def click_cancel(self) -> None:
        self._cancel_button.click()
