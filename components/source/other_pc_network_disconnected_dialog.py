"""Source PC's "The other PC isn't connected to a network." dialog -- shown when the
Target PC loses its network connection mid-transfer. Confirmed from a user-supplied
screenshot (2026-10-14); the Source-side mirror of
components.target.common_dialogs.OtherPcNetworkDisconnectedDialog (there, "the other
PC" means Source; here, it means Target). Treated the same way: an immediate,
unrecoverable failure -- nothing Source can retry locally when the OTHER machine lost
connectivity -- so this is a pure click_cancel_transfer() action; callers check
is_showing() first, then abort the whole run.
"""

from components.base_component import BaseComponent
from locators.source.other_pc_network_disconnected_dialog import CANCEL_TRANSFER_BUTTON_LOCATOR


class OtherPcNetworkDisconnectedDialog:
    def __init__(self, app_session):
        self._cancel_transfer_button = BaseComponent(
            app_session, *CANCEL_TRANSFER_BUTTON_LOCATOR, "SourceCancelTransferButton"
        )

    def click_cancel_transfer(self, timeout: float = 2.0) -> None:
        """Clicks "Cancel transfer". Callers check is_showing() first and only call
        this once they already know the dialog is present -- this never re-checks
        presence itself."""
        self._cancel_transfer_button.click(timeout=timeout)
