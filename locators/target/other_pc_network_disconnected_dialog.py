"""Locators for components.target.common_dialogs.OtherPcNetworkDisconnectedDialog ("The
other PC isn't connected to a network."). Confirmed from a user-supplied screenshot
(2026-10-12), shown layered over the transfer-progress screen -- distinct from
NetworkDisconnectedDialog ("This PC isn't connected to a network."), which is about
THIS machine's own connectivity. This one reports the REMOTE (Source) PC losing its
network connection, which Target cannot recover from locally -- has a "Cancel transfer"
button instead of "Check again".
"""

OTHER_PC_NETWORK_DISCONNECTED_HEADING_LOCATOR = (
    "xpath",
    '//*[@Name="The other PC isn\'t connected to a network."]',
)
CANCEL_TRANSFER_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Cancel transfer"]')
