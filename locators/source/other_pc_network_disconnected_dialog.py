"""Locators for
components.source.other_pc_network_disconnected_dialog.OtherPcNetworkDisconnectedDialog
-- click-target locator only. The heading assertion locator lives in
assertions/source/other_pc_network_disconnected_dialog.py instead.

Bug fixed here, confirmed via a user-supplied screenshot (2026-10-14): the button is
plain "Cancel", not "Cancel transfer" (the latter was never actually confirmed live --
see assertions/source/other_pc_network_disconnected_dialog.py's own docstring).
"""

CANCEL_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Cancel"]')
