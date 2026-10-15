"""Source PC's "We lost connection to your other PC." dialog -- shown when the Target
PC loses its network connection mid-transfer. The Source-side mirror of
components.target.common_dialogs.OtherPcNetworkDisconnectedDialog (there, "the other
PC" means Source; here, it means Target). Confirmed NOT fatal on Source (unlike
Target's own mirror-image dialog) -- just clicked through, same as
BatteryCriticallyLowDialog; see flows/source/common_dialogs.py's
check_other_pc_disconnected().
"""

from components.base_component import BaseComponent
from locators.source.other_pc_network_disconnected_dialog import CANCEL_BUTTON_LOCATOR


class OtherPcNetworkDisconnectedDialog:
    def __init__(self, app_session):
        self._cancel_button = BaseComponent(app_session, *CANCEL_BUTTON_LOCATOR, "SourceOtherPcDisconnectedCancelButton")

    def click_cancel(self, timeout: float = 2.0) -> None:
        """Clicks "Cancel". Callers check is_showing() first and only call this once
        they already know the dialog is present -- this never re-checks presence
        itself."""
        self._cancel_button.click(timeout=timeout)
