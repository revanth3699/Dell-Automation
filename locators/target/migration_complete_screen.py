"""Locators for components.target.migration_complete_screen.MigrationCompleteScreen --
shown after clicking "here" on MigrationSummaryScreen. Confirmed from a user-supplied
screenshot (2026-10-06): "We've successfully migrated your files", with "Congratulations,
this PC is ready to go... You can also download the PDF report with more details." --
"download the PDF report" is a real clickable link (blue, underlined); the rest of that
sentence is plain text.
"""

MIGRATION_COMPLETE_HEADING_LOCATOR = ("xpath", '//*[@Name="We\'ve successfully migrated your files"]')
DOWNLOAD_PDF_REPORT_LINK_LOCATOR = ("xpath", '//*[@Name="download the PDF report"]')
