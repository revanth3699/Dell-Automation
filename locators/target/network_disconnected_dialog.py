"""Locators for components.target.common_dialogs.NetworkDisconnectedDialog --
click-target locator only. The heading assertion locator lives in
assertions/target/network_disconnected_dialog.py instead.

Bug fixed here, confirmed live via a user-supplied screenshot (2026-10-15): the dialog
has exactly one button, "Cancel transfer" -- there is no "Check again" button on
Target's build. The locator this replaced never matched anything, so every click
attempt silently no-op'd (see components/target/common_dialogs.py's
NetworkDisconnectedDialog for the full story).
"""

NETWORK_DISCONNECTED_CANCEL_TRANSFER_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Cancel transfer"]')
