"""Locators for components.source.transfer_progress_screen -- the post-pairing
transfer-start sequence on Source PC: "We've successfully linked your PCs." (a brief
confirmation, not confirmed to always appear -- see LINKED_SUCCESS_HEADING_LOCATOR) ->
"Are you ready to start your migration?" -> "We're migrating your data now." ->
"Your migration summary is ready." (confirmed directly by the user, 2026-10-06/07; the
first three need no click, but this last one has a "Close" button, clicked per explicit
user direction, 2026-10-07). Confirmed from user-supplied screenshots. "We're searching
this PC for your files and settings." is deliberately not checked -- omitted per
explicit user direction, 2026-10-06.
"""

LINKED_SUCCESS_HEADING_LOCATOR = ("xpath", '//*[@Name="We\'ve successfully linked your PCs."]')
READY_TO_MIGRATE_HEADING_LOCATOR = ("xpath", '//*[@Name="Are you ready to start your migration?"]')
MIGRATING_DATA_HEADING_LOCATOR = ("xpath", '//*[@Name="We\'re migrating your data now."]')
MIGRATION_SUMMARY_READY_HEADING_LOCATOR = ("xpath", '//*[@Name="Your migration summary is ready."]')
MIGRATION_SUMMARY_CLOSE_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Close"]')
