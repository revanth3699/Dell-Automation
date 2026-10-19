"""Target-role "Admin access is required" precheck-failure dialog (FatalPrecheckModel for
the 'notAdmin' overlay) -- actions only: Cancel transfer, which returns to the Welcome
screen. See assertions/target/not_admin_dialog.py's is_showing().

Verified against source, not live: rebit TargetPc.UI web/src/App.tsx +
screens/precheck/FatalPrecheckModel.tsx; resx key Buttons_CancelTransfer.
"""

from components.base_component import BaseComponent
from locators.target.not_admin_dialog import CANCEL_TRANSFER_BUTTON_LOCATOR


class NotAdminDialog:
    def __init__(self, app_session):
        self._cancel_transfer_button = BaseComponent(
            app_session, *CANCEL_TRANSFER_BUTTON_LOCATOR, "NotAdminCancelTransferButton"
        )

    def click_cancel_transfer(self) -> None:
        self._cancel_transfer_button.click()
