"""Target-role "We're transferring your files and settings" screen (MigratingStage) --
actions only. Its one user action is the header Cancel link, which opens
components.target.cancel_migration_confirm_modal.CancelMigrationConfirmModal rather than
cancelling outright. The heading check is
assertions.target.transfer_progress_screen.is_showing() (already existing -- reused,
not duplicated here).

Verified against source, not live: rebit TargetPc.UI
web/src/screens/migration-run/MigratingStage.tsx + components/stage/StagePanelHeader.tsx;
resx key Buttons_Cancel.
"""

from components.base_component import BaseComponent
from locators.target.migrating_screen import CANCEL_LINK_LOCATOR


class MigratingScreen:
    def __init__(self, app_session):
        self._cancel_link = BaseComponent(app_session, *CANCEL_LINK_LOCATOR, "MigratingCancelLink")

    def click_cancel(self) -> None:
        self._cancel_link.click()
