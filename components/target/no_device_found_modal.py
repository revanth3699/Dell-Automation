"""Target-role "Connect your other PC to <network>" discovery-timeout modal
(NoDeviceFoundModal) -- actions only: Cancel transfer, which abandons discovery. See
assertions/target/no_device_found_modal.py's is_showing().

Verified against source, not live: rebit TargetPc.UI
web/src/screens/migration-setup/NoDeviceFoundModal.tsx; resx key Buttons_CancelTransfer.
"""

from components.base_component import BaseComponent
from locators.target.no_device_found_modal import CANCEL_TRANSFER_BUTTON_LOCATOR


class NoDeviceFoundModal:
    def __init__(self, app_session):
        self._cancel_transfer_button = BaseComponent(
            app_session, *CANCEL_TRANSFER_BUTTON_LOCATOR, "NoDeviceFoundCancelTransferButton"
        )

    def click_cancel_transfer(self) -> None:
        self._cancel_transfer_button.click()
