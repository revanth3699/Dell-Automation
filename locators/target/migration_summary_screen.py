"""Locators for components.target.migration_summary_screen.MigrationSummaryScreen --
shown once the transfer finishes ("We're moving your files and settings" clears).
Confirmed from a user-supplied screenshot (2026-10-06): "Here's a summary of your
migration results", with "Your migration was run on <date>. Click here to view the
details." -- only the single word "here" is a real clickable link; the rest of that
sentence is plain text.

MIGRATION_SUCCESS_HEADING_LOCATOR uses this confirmed, literally-visible heading text
(corrected 2026-10-06 per direct user clarification) -- an earlier version used "We have
successfully migrated your files", which was never actually seen in the supplied
screenshot and has been replaced.
"""

MIGRATION_SUCCESS_HEADING_LOCATOR = ("xpath", '//*[@Name="Here\'s a summary of your migration results"]')

# Bug fixed here, confirmed directly by the user (2026-10-09) via live screenshots:
# this screen also has a "Finish" link (top right) -- the actual next step in the real
# flow. The "here" link (VIEW_DETAILS_LINK_LOCATOR) used to be clicked instead; that was
# wrong -- clicking "here" doesn't advance to the real completion screen
# ("Your migration is now complete"), "Finish" does.
FINISH_LINK_LOCATOR = ("xpath", '//*[@Name="Finish"]')
