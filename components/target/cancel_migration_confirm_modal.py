"""Target-role "Are you sure you want to cancel?" confirmation modal, shown after the
Migrating screen's Cancel link (components/target/migrating_screen.py) is clicked. The
migration keeps running while this is open; "Yes, cancel" sends the real cancel, "No,
continue" just dismisses. See
assertions/target/cancel_migration_confirm_modal.py's is_showing().

Verified against source, not live: rebit TargetPc.UI
web/src/screens/migration-run/CancelMigrationConfirmModal.tsx; resx keys
MigratingCancelConfirm_Yes, MigratingCancelConfirm_No.
"""

from components.base_component import BaseComponent
from locators.target.cancel_migration_confirm_modal import (
    NO_CONTINUE_BUTTON_LOCATOR,
    YES_CANCEL_BUTTON_LOCATOR,
)


class CancelMigrationConfirmModal:
    def __init__(self, app_session):
        self._yes_cancel_button = BaseComponent(app_session, *YES_CANCEL_BUTTON_LOCATOR, "YesCancelButton")
        self._no_continue_button = BaseComponent(app_session, *NO_CONTINUE_BUTTON_LOCATOR, "NoContinueButton")

    def click_yes_cancel(self) -> None:
        self._yes_cancel_button.click()

    def click_no_continue(self) -> None:
        self._no_continue_button.click()
