"""Expected heading text + locator + assertion function for
components.target.cancel_migration_confirm_modal.CancelMigrationConfirmModal -- the
"Are you sure you want to cancel?" confirmation shown after clicking the Migrating
screen's Cancel link (and reused by App.tsx for the window-X close mid-migration).

Verified against source, not live: rebit TargetPc.UI
web/src/screens/migration-run/CancelMigrationConfirmModal.tsx renders a PopUpModel with
title t('MigratingCancelConfirm_Title') = "Are you sure you want to cancel?"
(Resources/Resources.resx). Apostrophe-free, so matched exactly. Never a click target,
so it lives here.
"""

from assertions.common import text_exists

HEADING_TEXT = "Are you sure you want to cancel?"
CANCEL_MIGRATION_CONFIRM_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(
        session, CANCEL_MIGRATION_CONFIRM_HEADING_LOCATOR, "CancelMigrationConfirmHeading", timeout=timeout
    )
