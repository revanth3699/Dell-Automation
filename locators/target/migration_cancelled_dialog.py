"""Locators for components.target.migration_cancelled_dialog.MigrationCancelledDialog --
click-target locator only. The heading assertion locator lives in
assertions/target/migration_cancelled_dialog.py instead.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/migration-run/MigrationCancelledModal.tsx renders a single-button
PopUpModelFooter whose primary DDSButton is t('Buttons_TryAgain') = "Try again"
(Resources/Resources.resx). Same accessible Name as ConnectionLostDialog's Try again
button -- callers must check this dialog's own heading first.
"""

TRY_AGAIN_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Try again"]')
