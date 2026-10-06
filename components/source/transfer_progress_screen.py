"""Source-role post-pairing transfer-start screens: "We're searching this PC for your
files and settings." -> "Are you ready to start your migration?" (confirmed directly by
the user, 2026-10-06: both auto-advance on their own, no button click needed -- these
are just text assertions confirming the expected sequence is actually happening).
"""

from components.base_component import BaseComponent
from locators.source.transfer_progress_screen import (
    READY_TO_MIGRATE_HEADING_LOCATOR,
    SEARCHING_FILES_HEADING_LOCATOR,
)


class TransferProgressScreen:
    def __init__(self, app_session):
        self._searching_heading = BaseComponent(app_session, *SEARCHING_FILES_HEADING_LOCATOR, "SearchingFilesHeading")
        self._ready_heading = BaseComponent(app_session, *READY_TO_MIGRATE_HEADING_LOCATOR, "ReadyToMigrateHeading")

    def is_searching(self, timeout: float = 2.0) -> bool:
        return self._searching_heading.exists(timeout=timeout)

    def is_ready_to_migrate(self, timeout: float = 2.0) -> bool:
        return self._ready_heading.exists(timeout=timeout)
