"""Source-role post-pairing transfer sequence: "We've successfully linked your PCs."
-> "Are you ready to start your migration?" -> "We're migrating your data now." ->
"Your migration summary is ready." (the real final screen on Source -- has the "Close"
button that's actually clicked). The first three are just text assertions confirming
the expected sequence is actually happening, no click needed.

Bug fixed here, confirmed directly by the user via a live run (2026-10-13): this used
to wait for a LATER screen, "We've completed your migration.", before clicking Close --
on a real run that text never appeared, even though "Your migration summary is ready."
(with its own Close button) was sitting there visible and clickable the whole time.
Close is now clicked directly here instead, confirmed via BOTH the heading and the
body text ("We've finished moving your files and settings. Check your other PC for a
summary of what was moved."). "We're searching this PC for your files and settings."
is deliberately not checked here -- omitted per explicit user direction, 2026-10-06,
since it's a weak/slow gate tied to Target's own pace.
"""

from components.base_component import BaseComponent
from locators.source.transfer_progress_screen import (
    LINKED_SUCCESS_HEADING_LOCATOR,
    MIGRATING_DATA_HEADING_LOCATOR,
    MIGRATION_SUMMARY_BODY_LOCATOR,
    MIGRATION_SUMMARY_CLOSE_BUTTON_LOCATOR,
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
        self._summary_body = BaseComponent(app_session, *MIGRATION_SUMMARY_BODY_LOCATOR, "MigrationSummaryBody")
        self._summary_close_button = BaseComponent(
            app_session, *MIGRATION_SUMMARY_CLOSE_BUTTON_LOCATOR, "MigrationSummaryCloseButton"
        )

    def is_linked_success(self, timeout: float = 2.0) -> bool:
        return self._linked_success_heading.exists(timeout=timeout)

    def is_ready_to_migrate(self, timeout: float = 2.0) -> bool:
        return self._ready_heading.exists(timeout=timeout)

    def is_migrating(self, timeout: float = 2.0) -> bool:
        return self._migrating_heading.exists(timeout=timeout)

    def is_summary_confirmed(self, timeout: float = 2.0) -> bool:
        """Confirmed via a live screenshot (2026-10-13): both the heading ("Your
        migration summary is ready.") AND the body text underneath it ("...Check your
        other PC for a summary of what was moved.") together are what confirm this is
        genuinely the final screen -- require both, not just the heading."""
        return self._summary_ready_heading.exists(timeout=timeout) and self._summary_body.exists(timeout=timeout)

    def close_summary(self) -> None:
        self._summary_close_button.click()
