"""Locators for components.source.transfer_progress_screen -- the post-pairing
transfer-start sequence on Source PC: "We've successfully linked your PCs." (a brief
confirmation, not confirmed to always appear -- see LINKED_SUCCESS_HEADING_LOCATOR) ->
"Are you ready to start your migration?" -> "We're migrating your data now." ->
"Your migration summary is ready." (the real final screen -- has its own Close button).

Bug fixed here, confirmed directly by the user via a live run (2026-10-13): this used
to treat "Your migration summary is ready." as a pure text confirmation and wait for a
LATER screen, "We've completed your migration." (shown only once Target PC's own user
clicks Finish and returns to its home screen), before clicking Close. On a real run,
that later text never appeared within a long wait even though "Your migration summary
is ready." -- with its own Close button, confirmed via a live screenshot -- was sitting
there the whole time, visible and clickable. Reverted: Close is now clicked directly on
"Your migration summary is ready.", confirmed via BOTH its heading and its body text
("We've finished moving your files and settings. Check your other PC for a summary of
what was moved.") for a stronger signal than the heading alone. "We're searching this
PC for your files and settings." remains deliberately not checked -- omitted per
explicit user direction, 2026-10-06.
"""

LINKED_SUCCESS_HEADING_LOCATOR = ("xpath", '//*[@Name="We\'ve successfully linked your PCs."]')
READY_TO_MIGRATE_HEADING_LOCATOR = ("xpath", '//*[@Name="Are you ready to start your migration?"]')
MIGRATING_DATA_HEADING_LOCATOR = ("xpath", '//*[@Name="We\'re migrating your data now."]')
MIGRATION_SUMMARY_READY_HEADING_LOCATOR = ("xpath", '//*[@Name="Your migration summary is ready."]')
# Confirmed via a live screenshot (2026-10-13): the body text shown under the heading,
# used alongside it as a stronger "migration summary genuinely ready" confirmation than
# the heading alone -- same two-texts pattern used elsewhere in this project (e.g.
# WelcomeBackScreen.is_home_confirmed()).
MIGRATION_SUMMARY_BODY_LOCATOR = (
    "xpath",
    '//*[contains(@Name, "Check your other PC for a summary of what was moved")]',
)
MIGRATION_SUMMARY_CLOSE_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Close"]')
