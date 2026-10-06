"""Locators for components.source.transfer_progress_screen -- the post-pairing
transfer-start sequence on Source PC: "We've successfully linked your PCs." (a brief
confirmation, not confirmed to always appear -- see LINKED_SUCCESS_HEADING_LOCATOR) ->
"Are you ready to start your migration?" (confirmed directly by the user, 2026-10-06:
this auto-advances on its own, no button click needed). Confirmed from user-supplied
screenshots (2026-10-06). "We're searching this PC for your files and settings." is
deliberately not checked -- omitted per explicit user direction, 2026-10-06.
"""

LINKED_SUCCESS_HEADING_LOCATOR = ("xpath", '//*[@Name="We\'ve successfully linked your PCs."]')
READY_TO_MIGRATE_HEADING_LOCATOR = ("xpath", '//*[@Name="Are you ready to start your migration?"]')
