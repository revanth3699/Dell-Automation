"""Source PC's "Your regional settings aren't supported." dialog -- "To continue,
you'll need to update to a supported region." Confirmed from a user-supplied
screenshot (2026-10-14). Clicking "Close" closes the app entirely -- see
assertions/source/regional_settings_not_supported_dialog.py's is_showing() and
flows/source/common_dialogs.py's raise_if_regional_settings_not_supported() for why
this is fatal, not a dialog to click through and continue past.
"""

from components.base_component import BaseComponent
from locators.source.regional_settings_not_supported_dialog import CLOSE_BUTTON_LOCATOR


class RegionalSettingsNotSupportedDialog:
    def __init__(self, app_session):
        self._close_button = BaseComponent(
            app_session, *CLOSE_BUTTON_LOCATOR, "RegionalSettingsNotSupportedCloseButton"
        )

    def click_close(self) -> None:
        self._close_button.click()
