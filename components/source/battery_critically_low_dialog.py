"""Source PC's "Your battery is critically low." dialog -- "You'll need to plug this
PC into AC power to continue." Confirmed from a user-supplied screenshot (2026-10-14).
See assertions/source/battery_critically_low_dialog.py's is_showing().

Bug fixed here, per explicit user direction (2026-10-13): this used to dismiss the
dialog immediately, no wait first (reasoning at the time: this dialog reports the
battery as already critically low, not just a warning, unlike Target's
PlugIntoAcPowerDialog). Reversed per the user's own direction -- now waits
BATTERY_CRITICALLY_LOW_DELAY_SECONDS before clicking Cancel, same "give the user a
real chance to plug in" pattern as PlugIntoAcPowerDialog
(components/target/common_dialogs.py).
"""

import time

from components.base_component import BaseComponent
from locators.source.battery_critically_low_dialog import CANCEL_BUTTON_LOCATOR


class BatteryCriticallyLowDialog:
    BATTERY_CRITICALLY_LOW_DELAY_SECONDS = 10.0

    def __init__(self, app_session):
        self._cancel_button = BaseComponent(app_session, *CANCEL_BUTTON_LOCATOR, "BatteryCriticallyLowCancelButton")

    def click_cancel(self) -> None:
        time.sleep(self.BATTERY_CRITICALLY_LOW_DELAY_SECONDS)
        self._cancel_button.click()
