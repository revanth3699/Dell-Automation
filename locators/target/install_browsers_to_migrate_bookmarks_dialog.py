"""Locators for components.target.common_dialogs.InstallBrowsersToMigrateBookmarksDialog
-- click-target locators only. The heading assertion locator lives in
assertions/target/install_browsers_to_migrate_bookmarks_dialog.py instead.

Bug fixed here, confirmed via a user-supplied screenshot (2026-10-19): the button
previously named "Rescan" is actually named "Resume" -- the live dialog shows "Resume
after installing, or Skip to continue without transferring bookmarks."
"""

RESUME_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Resume"]')
SKIP_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Skip"]')
