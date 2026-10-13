"""Locators for components.target.transfer_receive_screen.TransferReceiveScreen --
click-target locator only. The heading assertion locator lives in
assertions/target/transfer_receive_screen.py instead.

BRING_EVERYTHING_OVER_BUTTON_LOCATOR's real accessible Name is "Migrate now" --
confirmed live (2026-10-06) via a diagnostic //Button dump, NOT "Bring everything over
for me" (that's the adjacent visible label text, a different string from the icon-only
button's own accessible Name).
"""

BRING_EVERYTHING_OVER_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Migrate now"]')
