"""Source PC's "This PC isn't connected to a network." dialog. Same generic
connectivity-check modal as components/target/common_dialogs.py's
NetworkDisconnectedDialog -- confirmed from the same user-supplied screenshots
(2026-10-09); treated as symmetric across both roles since the body text ("Connect both
of your PCs to the same network to continue") is explicitly about both PCs, not
specific to one side's screen.

Per explicit user direction (2026-10-14): the existence check (is_showing()) moved out
to assertions/source/network_disconnected_dialog.py, called directly from flows/.

Cancel is the dialog's only button. There is no "Check again" button on the Source side
(verified against MigrateToDell.UI source, 2026-10-19 -- see
locators/source/network_disconnected_dialog.py): the dialog clears itself and re-runs
the precheck when the network returns, so flows wait it out rather than clicking any
retry. The former click_check_again() action was removed on 2026-10-22 once that was
confirmed on both roles (the Target's RecoverablePrecheckModel likewise dropped its
Check again button).
"""

from components.base_component import BaseComponent
from locators.source.network_disconnected_dialog import CANCEL_BUTTON_LOCATOR


class NetworkDisconnectedDialog:
    def __init__(self, app_session):
        self._cancel_button = BaseComponent(app_session, *CANCEL_BUTTON_LOCATOR, "NetworkDisconnectedCancelButton")

    def click_cancel(self) -> None:
        """The dialog's only button (2026-10-19, verified against MigrateToDell.UI
        source, not live -- see locators/source/network_disconnected_dialog.py). Opens
        the Are you sure you want to cancel? prompt."""
        self._cancel_button.click(timeout=2.0)
