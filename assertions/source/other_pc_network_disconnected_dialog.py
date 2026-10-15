"""Expected heading text + locator + assertion function for
components.source.other_pc_network_disconnected_dialog.OtherPcNetworkDisconnectedDialog
("We lost connection to your other PC." -- "Make sure both of your PCs are connected
to the <network> network."). Shown when the Target PC loses its network connection
mid-transfer -- the Source-side mirror of
assertions/target/other_pc_network_disconnected_dialog.py (there, "the other PC" means
Source; here, it means Target). Distinct from NetworkDisconnectedDialog ("This PC
isn't connected to a network."), which is about THIS machine's own connectivity.
Never a click target, so it lives here rather than in locators/ -- per explicit user
direction (2026-10-14).

Bug fixed here, confirmed via user-supplied screenshots (2026-10-14): the previous
heading, "The other PC isn't connected to a network.", and its "Cancel transfer"
button were never actually confirmed live -- the real screen reads "We lost connection
to your other PC." with a plain "Cancel" button. Replaced with the confirmed text.
Also confirmed: clicking Cancel triggers ConfirmCancelDialog ("Are you sure you want to
cancel?"), same as BatteryCriticallyLowDialog -- see
flows/source/common_dialogs.py's check_other_pc_disconnected().
"""

from assertions.common import text_exists

HEADING_TEXT = "We lost connection to your other PC."
OTHER_PC_NETWORK_DISCONNECTED_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(
        session, OTHER_PC_NETWORK_DISCONNECTED_HEADING_LOCATOR, "OtherPcNetworkDisconnectedHeading", timeout=timeout
    )
