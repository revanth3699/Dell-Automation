"""Locators for components.target.common_dialogs.MigrationErrorDialog -- the body
locator only (read via get_text() for diagnostics, not an existence check). The heading
assertion locator + is_showing() live in assertions/target/migration_error_dialog.py.
"""

from assertions.target.migration_error_dialog import BODY_CONTAINS_TEXT

MIGRATION_ERROR_BODY_LOCATOR = ("xpath", f'//*[contains(@Name, "{BODY_CONTAINS_TEXT}")]')

# Added 2026-10-19 (verified against rebit source, not live). FailureModal.tsx's
# primaryLabelKeyFor(): the single footer button (a PopUpModelFooter DDSButton) reads
# Buttons_Ok ("Ok") when state.dismissible (Erase started on old PC), Buttons_CancelTransfer
# when state.titleKey is set (version mismatch), and Buttons_Close otherwise (the generic
# "Something went wrong" dead-end). Close excludes the native title-bar CloseButton -- same
# reasoning as locators/target/regional_settings_not_supported_dialog.py.
CLOSE_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Close" and not(@AutomationId="CloseButton")]')
OK_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Ok"]')
CANCEL_TRANSFER_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Cancel transfer"]')
