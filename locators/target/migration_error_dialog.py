"""Locators for components.target.common_dialogs.MigrationErrorDialog -- the body
locator only (read via get_text() for diagnostics, not an existence check). The heading
assertion locator + is_showing() live in assertions/target/migration_error_dialog.py.
"""

from assertions.target.migration_error_dialog import BODY_CONTAINS_TEXT

MIGRATION_ERROR_BODY_LOCATOR = ("xpath", f'//*[contains(@Name, "{BODY_CONTAINS_TEXT}")]')
