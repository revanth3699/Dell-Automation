"""Locators for components.target.migrating_screen.MigratingScreen -- click-target
locator only. The heading assertion for this screen already exists in
assertions/target/transfer_progress_screen.py (Migrating_Title) and is reused, not
duplicated.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/migration-run/MigratingStage.tsx passes onAction to StagePanel with no
actionLabel (only while state.isMigrating && state.canCancel), so
components/stage/StagePanelHeader.tsx renders a DDSLink labelled its default
t('Buttons_Cancel') = "Cancel" (Resources/Resources.resx) plus an aria-hidden close-x
icon. A link, not a Button, hence //* rather than //Button. Clicking it opens the
"Are you sure you want to cancel?" modal (locators/target/cancel_migration_confirm_modal.py)
rather than cancelling directly.
"""

CANCEL_LINK_LOCATOR = ("xpath", '//*[@Name="Cancel"]')
