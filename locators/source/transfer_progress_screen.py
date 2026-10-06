"""Locators for components.source.transfer_progress_screen -- the post-pairing
transfer-start sequence on Source PC: "We're searching this PC for your files and
settings." (automatic scan) -> "Are you ready to start your migration?" (confirmed
directly by the user, 2026-10-06: this auto-advances on its own, no button click
needed). Confirmed from a user-supplied screenshot (2026-10-06).
"""

SEARCHING_FILES_HEADING_LOCATOR = ("xpath", '//*[@Name="We\'re searching this PC for your files and settings."]')
READY_TO_MIGRATE_HEADING_LOCATOR = ("xpath", '//*[@Name="Are you ready to start your migration?"]')
