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

# Added 2026-10-19 (verified against rebit source, not live). MigrationDoneView.tsx renders
# four tiles as <button className=tile> (IconBadge + label span): Buttons_ViewSummary ("View
# transfer summary"), MigrationDone_TellUsHowWeDid ("Tell us how we did"),
# MigrationDone_MigrateMoreData (TRANSFER_MORE_DATA_BUTTON_LOCATOR above) and
# MigrationDone_LearnAboutErase ("Erase your old PC"). contains() rather than an exact match
# because the tile's accessible name is computed from its whole content and the icon badge
# may contribute text -- unverified live. The top-right StageCard cancel link is relabelled
# Buttons_Close ("Close", Channels.migrationDoneClose, no x icon); it excludes the native
# title-bar CloseButton, same as locators/target/regional_settings_not_supported_dialog.py.
VIEW_SUMMARY_BUTTON_LOCATOR = ("xpath", '//Button[contains(@Name, "View transfer summary")]')
TELL_US_HOW_WE_DID_BUTTON_LOCATOR = ("xpath", '//Button[contains(@Name, "Tell us how we did")]')
ERASE_OLD_PC_BUTTON_LOCATOR = ("xpath", '//Button[contains(@Name, "Erase your old PC")]')
CLOSE_LINK_LOCATOR = ("xpath", '//*[@Name="Close" and not(@AutomationId="CloseButton")]')
