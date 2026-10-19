"""Expected heading text + locator + assertion function for
components.target.connection_lost_dialog.ConnectionLostDialog -- shown over whichever
screen is current when the live control-channel connection to the other PC drops.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/precheck/ConnectionLostModal.tsx renders a PopUpModel whose title is the
bridge-supplied state.title, which Bridge/Handlers/ConnectionLostScreenAdapter.cs
hard-codes as TitleText = "Connection lost" (NOT a resx key). Short and apostrophe-free,
so matched exactly. Never a click target, so it lives here.
"""

from assertions.common import text_exists

HEADING_TEXT = "Connection lost"
CONNECTION_LOST_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(session, CONNECTION_LOST_HEADING_LOCATOR, "ConnectionLostHeading", timeout=timeout)
