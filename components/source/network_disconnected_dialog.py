"""Source PC's "This PC isn't connected to a network." dialog. Same generic
connectivity-check modal as components/target/common_dialogs.py's
NetworkDisconnectedDialog -- confirmed from the same user-supplied screenshots
(2026-10-09); treated as symmetric across both roles since the body text ("Connect both
of your PCs to the same network to continue") is explicitly about both PCs, not
specific to one side's screen.
"""

import time

from components.base_component import BaseComponent
from locators.source.network_disconnected_dialog import CHECK_AGAIN_BUTTON_LOCATOR, HEADING_LOCATOR


class NetworkDisconnectedDialog:
    """Per explicit user direction: waits CHECK_AGAIN_DELAY_SECONDS before clicking
    Check again (rather than immediately), since the underlying network condition is
    likely transient -- an instant re-check would probably just hit the same failure
    again."""

    CHECK_AGAIN_DELAY_SECONDS = 30.0

    def __init__(self, app_session):
        self._heading = BaseComponent(app_session, *HEADING_LOCATOR, "NetworkDisconnectedHeading")
        self._check_again_button = BaseComponent(app_session, *CHECK_AGAIN_BUTTON_LOCATOR, "CheckAgainButton")

    def is_showing(self, timeout: float = 0.1) -> bool:
        return self._heading.exists(timeout=timeout)

    def accept(self, timeout: float = 2.0) -> bool:
        """Clicks "Check again" if the dialog is showing, after waiting
        CHECK_AGAIN_DELAY_SECONDS first. Returns whether it was present at all (same
        pattern as TrustNetworkDialog.accept())."""
        if not self._heading.exists(timeout=timeout):
            return False
        time.sleep(self.CHECK_AGAIN_DELAY_SECONDS)
        self._check_again_button.click(timeout=2.0)
        return True
