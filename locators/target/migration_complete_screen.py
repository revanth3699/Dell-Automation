"""Locators for components.target.migration_complete_screen.MigrationCompleteScreen --
click-target locators only. The heading assertion locator lives in
assertions/target/migration_complete_screen.py instead.

Confirmed directly by the user (2026-10-09) via a live screenshot: "download a PDF" is
the real clickable link (blue, underlined); a separate "Back to Home" link sits top
right and is the actual way off this screen.
"""

DOWNLOAD_PDF_LINK_LOCATOR = ("xpath", '//*[@Name="download a PDF"]')
BACK_TO_HOME_LINK_LOCATOR = ("xpath", '//*[@Name="Back to Home"]')
