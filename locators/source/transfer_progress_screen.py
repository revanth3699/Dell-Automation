"""Locators for components.source.transfer_progress_screen -- the post-pairing
transfer-start sequence on Source PC: "We've successfully linked your PCs." (a brief
confirmation, not confirmed to always appear -- see LINKED_SUCCESS_HEADING_LOCATOR) ->
"Are you ready to start your migration?" -> "We're migrating your data now." ->
"Your migration summary is ready." -> "We've completed your migration." (confirmed
directly by the user, 2026-10-09: appears only once Target PC's own user clicks Finish
and Target is redirected back to its home screen -- a separate, later screen from
"Your migration summary is ready.", not the same screen with different wording).

Bug fixed here, confirmed directly by the user (2026-10-09): this flow used to click
Close on "Your migration summary is ready." -- per explicit user direction, that's no
longer clicked at all (now a pure text confirmation, same as the three screens before
it); the actual Close click happens on "We've completed your migration." instead, the
real final screen. "We're searching this PC for your files and settings." remains
deliberately not checked -- omitted per explicit user direction, 2026-10-06.
"""

LINKED_SUCCESS_HEADING_LOCATOR = ("xpath", '//*[@Name="We\'ve successfully linked your PCs."]')
READY_TO_MIGRATE_HEADING_LOCATOR = ("xpath", '//*[@Name="Are you ready to start your migration?"]')
MIGRATING_DATA_HEADING_LOCATOR = ("xpath", '//*[@Name="We\'re migrating your data now."]')
MIGRATION_SUMMARY_READY_HEADING_LOCATOR = ("xpath", '//*[@Name="Your migration summary is ready."]')
MIGRATION_COMPLETE_HEADING_LOCATOR = ("xpath", '//*[@Name="We\'ve completed your migration."]')
# Confirmed directly by the user via a live screenshot (2026-10-09): the body text
# shown under the heading, used alongside it as the real "migration succeeded"
# confirmation (same two-texts-stronger-than-one pattern as
# WelcomeBackScreen.is_home_confirmed()). Matched via contains() on a stable substring
# rather than the full paragraph, since the trailing "Erase this PC." is rendered bold
# (a separate run in the accessibility tree) and may not share one Name with the rest
# of the sentence.
MIGRATION_COMPLETE_BODY_LOCATOR = (
    "xpath",
    '//*[contains(@Name, "You\'ve successfully migrated your data to your new PC")]',
)
MIGRATION_COMPLETE_CLOSE_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Close"]')
