"""Locators for components.target.transfer_receive_screen.TransferReceiveScreen
("Your files are ready to move" -- shown after pairing succeeds and Target finishes
preparing/scanning what will be transferred). Confirmed from a user-supplied
screenshot (2026-10-06).

BRING_EVERYTHING_OVER_BUTTON_LOCATOR is NOT yet confirmed live: in the screenshot the
button is an icon-only blue circle with an arrow, no visible text on the button itself
-- "Bring everything over for me" is the adjacent label text, which may or may not also
be the button's own accessible Name. Confirm/adjust once hit for real.
"""

FILES_READY_HEADING_LOCATOR = ("xpath", '//*[@Name="Your files are ready to move"]')
BRING_EVERYTHING_OVER_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Bring everything over for me"]')
