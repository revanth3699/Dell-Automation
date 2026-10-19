"""Locators for components.target.cancel_migration_confirm_modal.CancelMigrationConfirmModal
-- click-target locators only. The heading assertion locator lives in
assertions/target/cancel_migration_confirm_modal.py instead.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/migration-run/CancelMigrationConfirmModal.tsx uses a PopUpModelFooter
(two DDSButtons): secondary t('MigratingCancelConfirm_Yes') = "Yes, cancel" and primary
t('MigratingCancelConfirm_No') = "No, continue" (Resources/Resources.resx).
"""

YES_CANCEL_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Yes, cancel"]')
NO_CONTINUE_BUTTON_LOCATOR = ("xpath", '//Button[@Name="No, continue"]')
