"""Target-role "The transfer was cancelled on your other PC" dialog
(MigrationCancelledModal) -- actions only: Try again, its only button (Escape/dismiss
also routes to Try again, since the pairing is already dead). See
assertions/target/migration_cancelled_dialog.py's is_showing().

Verified against source, not live: rebit TargetPc.UI
web/src/screens/migration-run/MigrationCancelledModal.tsx; resx key Buttons_TryAgain.
"""

from components.base_component import BaseComponent
from locators.target.migration_cancelled_dialog import TRY_AGAIN_BUTTON_LOCATOR


class MigrationCancelledDialog:
    def __init__(self, app_session):
        self._try_again_button = BaseComponent(
            app_session, *TRY_AGAIN_BUTTON_LOCATOR, "MigrationCancelledTryAgainButton"
        )

    def click_try_again(self) -> None:
        self._try_again_button.click()
