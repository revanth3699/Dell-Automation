"""Locators for components.target.common_dialogs.RegionalSettingsNotSupportedDialog --
click-target locator only. The heading assertion locator lives in
assertions/target/regional_settings_not_supported_dialog.py instead.

Deliberately excludes AutomationId="CloseButton" -- that's the app's own native window
caption close button (see components/target/app_window.py's CLOSE_BUTTON_LOCATOR), a
plain //Button[@Name="Close"] risks matching it instead of this dialog's own Close
button, since find_element returns the first document-order match (same ambiguity
already documented in locators/target/restore_pages_dialog.py for a different dialog).
Not confirmed live which element a bare match would actually hit first -- this
exclusion is a deliberately safe-by-construction choice, not one verified against the
real element tree.
"""

CLOSE_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Close" and not(@AutomationId="CloseButton")]')
