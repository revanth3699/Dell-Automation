"""Locators for components.source.network_disconnected_dialog.NetworkDisconnectedDialog
("This PC isn't connected to a network."). Same generic connectivity-check modal as
locators/target/network_disconnected_dialog.py -- confirmed from the same
user-supplied screenshots (2026-10-09); treated as symmetric across both roles since
the body text ("Connect both of your PCs to the same network to continue") is
explicitly about both PCs, not specific to one side's screen.
"""

HEADING_LOCATOR = ("xpath", '//*[@Name="This PC isn\'t connected to a network."]')
CHECK_AGAIN_BUTTON_LOCATOR = ("xpath", '//*[@Name="Check again"]')
