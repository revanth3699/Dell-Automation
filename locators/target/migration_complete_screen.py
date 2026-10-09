"""Locators for components.target.migration_complete_screen.MigrationCompleteScreen --
shown after clicking "Finish" on MigrationSummaryScreen. Confirmed directly by the user
(2026-10-09) via a live screenshot: "Your migration is now complete", with
"Congratulations, this PC is ready to go. Don't forget that you can erase your old PC
when you have completed your migration. You can also download a PDF with more
details." -- "download a PDF" is the real clickable link (blue, underlined); a separate
"Back to Home" link sits top right and is the actual way off this screen.

Bug fixed here, confirmed directly by the user (2026-10-09): the heading previously on
record here, "We've successfully migrated your files", was never actually seen live --
this is the real heading and real link text for this screen.
"""

MIGRATION_COMPLETE_HEADING_LOCATOR = ("xpath", '//*[@Name="Your migration is now complete"]')
DOWNLOAD_PDF_LINK_LOCATOR = ("xpath", '//*[@Name="download a PDF"]')
BACK_TO_HOME_LINK_LOCATOR = ("xpath", '//*[@Name="Back to Home"]')
