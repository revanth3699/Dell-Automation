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
VIEW_DETAILS_LINK_LOCATOR = ("xpath", '//*[@Name="here"]')
