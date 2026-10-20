"""Expected heading text + locator + assertion function for
components.target.migration_cancelled_dialog.MigrationCancelledDialog -- shown when the
OLD PC cancels the migration and its Data Assistant closes mid-session (engine
Error.Details FailureCode 2206).

Verified against source, not live: rebit TargetPc.UI
web/src/screens/migration-run/MigrationCancelledModal.tsx renders a PopUpModel titled
t('MigrationCancelled_Title') = "The transfer was cancelled on your other PC"
(Resources/Resources.resx). Apostrophe-free, but matched on the distinctive trailing
substring via contains() for resilience to minor copy edits. Never a click target, so
it lives here.
"""

from assertions.common import text_exists

HEADING_CONTAINS_TEXT = "cancelled on your other PC"
MIGRATION_CANCELLED_HEADING_LOCATOR = ("xpath", f'//*[contains(@Name, "{HEADING_CONTAINS_TEXT}")]')


def is_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(session, MIGRATION_CANCELLED_HEADING_LOCATOR, "MigrationCancelledHeading", timeout=timeout)
