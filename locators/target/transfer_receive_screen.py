"""Locators for components.target.transfer_receive_screen.TransferReceiveScreen
("Your files are ready to move" -- shown after pairing succeeds and Target finishes
preparing/scanning what will be transferred). Confirmed from a user-supplied
screenshot (2026-10-06).

BRING_EVERYTHING_OVER_BUTTON_LOCATOR's real accessible Name is "Migrate now" --
confirmed live (2026-10-06) via a diagnostic //Button dump, NOT "Bring everything over
for me" (that's the adjacent visible label text, a different string from the icon-only
button's own accessible Name).
"""

FILES_READY_HEADING_LOCATOR = ("xpath", '//*[@Name="Your files are ready to move"]')
BRING_EVERYTHING_OVER_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Migrate now"]')
