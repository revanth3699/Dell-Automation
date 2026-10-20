"""Target-role "Connection lost" dialog (ConnectionLostModal), shown when the
control-channel connection to the other PC drops unexpectedly -- actions only: Try
again (retries pairing / resumes) or Cancel transfer (closes the app). See
assertions/target/connection_lost_dialog.py's is_showing().

Verified against source, not live: rebit TargetPc.UI
web/src/screens/precheck/ConnectionLostModal.tsx; resx keys Buttons_TryAgain,
Buttons_CancelTransfer.
"""

from components.base_component import BaseComponent
from locators.target.connection_lost_dialog import (
    CANCEL_TRANSFER_BUTTON_LOCATOR,
    TRY_AGAIN_BUTTON_LOCATOR,
)


class ConnectionLostDialog:
    def __init__(self, app_session):
        self._try_again_button = BaseComponent(app_session, *TRY_AGAIN_BUTTON_LOCATOR, "ConnectionLostTryAgainButton")
        self._cancel_transfer_button = BaseComponent(
            app_session, *CANCEL_TRANSFER_BUTTON_LOCATOR, "ConnectionLostCancelTransferButton"
        )

    def click_try_again(self) -> None:
        self._try_again_button.click()

    def click_cancel_transfer(self) -> None:
        self._cancel_transfer_button.click()
