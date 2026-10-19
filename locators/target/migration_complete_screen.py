"""Locators for components.target.migration_complete_screen.MigrationCompleteScreen --
click-target locators only. The heading assertion locator lives in
assertions/target/migration_complete_screen.py instead.

Confirmed directly by the user (2026-10-09) via a live screenshot: "download a PDF" is
the real clickable link (blue, underlined).

Updated 2026-10-19 from rebit TargetPc.UI (commit 63e735d45, MigrationDoneView.tsx): the
top-right "Back to Home" link is gone -- that slot is now "Close", which ends the app. The
"Transfer more data" tile runs the same GoHome() path Back to Home did
(MigrationDonePageViewModel: MigrateMoreDataCommand and BackToHomeCommand both send
Migration.Stop, then return to WelcomePage), so it is the way back to the home screen now.
"""

DOWNLOAD_PDF_LINK_LOCATOR = ("xpath", '//*[@Name="download a PDF"]')
TRANSFER_MORE_DATA_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Transfer more data"]')
