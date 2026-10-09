"""Locators for components.target.common_dialogs.NetworkDisconnectedDialog ("This PC
isn't connected to a network."). Confirmed from two user-supplied screenshots
(2026-10-09), each showing the dialog layered over a different underlying screen -- a
generic connectivity-check modal that can appear at any point during a
pairing-dependent wait, not tied to one specific screen.
"""

NETWORK_DISCONNECTED_HEADING_LOCATOR = ("xpath", '//*[@Name="This PC isn\'t connected to a network."]')
CHECK_AGAIN_BUTTON_LOCATOR = ("xpath", '//*[@Name="Check again"]')
