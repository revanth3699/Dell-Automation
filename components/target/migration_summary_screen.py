"""Target-role migration-summary screen -- shown once the transfer finishes. Confirmed
from a user-supplied screenshot (2026-10-06): "Here's a summary of your migration
results", with a "Click here to view the details." sentence where only the word "here"
is a real clickable link.
"""

from components.base_component import BaseComponent
from locators.target.migration_summary_screen import MIGRATION_SUCCESS_HEADING_LOCATOR, VIEW_DETAILS_LINK_LOCATOR


class MigrationSummaryScreen:
    def __init__(self, app_session):
        self._success_heading = BaseComponent(
            app_session, *MIGRATION_SUCCESS_HEADING_LOCATOR, "MigrationSuccessHeading"
        )
        self._view_details_link = BaseComponent(app_session, *VIEW_DETAILS_LINK_LOCATOR, "ViewDetailsLink")

    def is_showing(self, timeout: float = 2.0) -> bool:
        return self._success_heading.exists(timeout=timeout)

    def click_view_details_link(self) -> None:
        self._view_details_link.click()
