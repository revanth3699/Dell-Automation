"""Source-role post-pairing transfer sequence: "We've successfully linked your PCs."
-> "Are you ready to start your migration?" -> "We're migrating your data now." ->
"Your migration summary is ready." -> "We've completed your migration." (confirmed
directly by the user, 2026-10-09: this last screen appears only once Target PC's own
user clicks Finish and Target is redirected back to its home screen -- a separate,
later screen, not the same screen as "Your migration summary is ready." with different
wording). All four earlier screens are just text assertions confirming the expected
sequence is actually happening, no click needed; "We've completed your migration." has
the "Close" button that's actually clicked.

Bug fixed here, confirmed directly by the user (2026-10-09): this used to click Close
on "Your migration summary is ready." -- per explicit user direction, that click moved
to "We've completed your migration." instead, since clicking Close any earlier was
premature (nothing bad necessarily happened, but it wasn't the app's own intended final
action). "We're searching this PC for your files and settings." is deliberately not
checked here -- omitted per explicit user direction, 2026-10-06, since it's a weak/slow
gate tied to Target's own pace.
"""

from components.base_component import BaseComponent
from locators.source.transfer_progress_screen import (
    LINKED_SUCCESS_HEADING_LOCATOR,
    MIGRATING_DATA_HEADING_LOCATOR,
    MIGRATION_COMPLETE_CLOSE_BUTTON_LOCATOR,
    MIGRATION_COMPLETE_HEADING_LOCATOR,
    MIGRATION_SUMMARY_READY_HEADING_LOCATOR,
    READY_TO_MIGRATE_HEADING_LOCATOR,
)


class TransferProgressScreen:
    def __init__(self, app_session):
        self._linked_success_heading = BaseComponent(
            app_session, *LINKED_SUCCESS_HEADING_LOCATOR, "LinkedSuccessHeading"
        )
        self._ready_heading = BaseComponent(app_session, *READY_TO_MIGRATE_HEADING_LOCATOR, "ReadyToMigrateHeading")
        self._migrating_heading = BaseComponent(
            app_session, *MIGRATING_DATA_HEADING_LOCATOR, "MigratingDataHeading"
        )
        self._summary_ready_heading = BaseComponent(
            app_session, *MIGRATION_SUMMARY_READY_HEADING_LOCATOR, "MigrationSummaryReadyHeading"
        )
        self._migration_complete_heading = BaseComponent(
            app_session, *MIGRATION_COMPLETE_HEADING_LOCATOR, "MigrationCompleteHeading"
        )
        self._migration_complete_close_button = BaseComponent(
            app_session, *MIGRATION_COMPLETE_CLOSE_BUTTON_LOCATOR, "MigrationCompleteCloseButton"
        )

    def is_linked_success(self, timeout: float = 2.0) -> bool:
        return self._linked_success_heading.exists(timeout=timeout)

    def is_ready_to_migrate(self, timeout: float = 2.0) -> bool:
        return self._ready_heading.exists(timeout=timeout)

    def is_migrating(self, timeout: float = 2.0) -> bool:
        return self._migrating_heading.exists(timeout=timeout)

    def is_summary_ready(self, timeout: float = 2.0) -> bool:
        return self._summary_ready_heading.exists(timeout=timeout)

    def is_migration_complete(self, timeout: float = 2.0) -> bool:
        return self._migration_complete_heading.exists(timeout=timeout)

    def close_migration_complete(self) -> None:
        self._migration_complete_close_button.click()
