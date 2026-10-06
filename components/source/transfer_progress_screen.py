"""Source-role post-pairing transfer-start screens: "We've successfully linked your
PCs." -> "Are you ready to start your migration?" (confirmed directly by the user,
2026-10-06: neither needs a button click -- these are just text assertions confirming
the expected sequence is actually happening). "We're searching this PC for your files
and settings." is deliberately not checked here -- omitted per explicit user direction,
2026-10-06, since it's a weak/slow gate tied to Target's own pace.
"""

from components.base_component import BaseComponent
from locators.source.transfer_progress_screen import (
    LINKED_SUCCESS_HEADING_LOCATOR,
    READY_TO_MIGRATE_HEADING_LOCATOR,
)


class TransferProgressScreen:
    def __init__(self, app_session):
        self._linked_success_heading = BaseComponent(
            app_session, *LINKED_SUCCESS_HEADING_LOCATOR, "LinkedSuccessHeading"
        )
        self._ready_heading = BaseComponent(app_session, *READY_TO_MIGRATE_HEADING_LOCATOR, "ReadyToMigrateHeading")

    def is_linked_success(self, timeout: float = 2.0) -> bool:
        return self._linked_success_heading.exists(timeout=timeout)

    def is_ready_to_migrate(self, timeout: float = 2.0) -> bool:
        return self._ready_heading.exists(timeout=timeout)
