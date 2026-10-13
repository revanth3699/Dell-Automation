"""Target-role migration-summary screen -- shown once the transfer finishes. Confirmed
from a user-supplied screenshot (2026-10-06): "Here's a summary of your migration
results", with a "Click here to view the details." sentence where only the word "here"
is a real clickable link.

Bug fixed here, confirmed directly by the user (2026-10-09) via live screenshots: this
screen is also the start of the REAL completion sequence -- click "Finish" (top right),
not "here", to advance to "Your migration is now complete"
(components/target/migration_complete_screen.py). Clicking "here" was the previous
(wrong) action; it doesn't lead anywhere useful for finishing the flow.

Per explicit user direction (2026-10-14): the existence check (is_showing()) moved out
to assertions/target/migration_summary_screen.py, called directly from flows/ -- this
class now holds only the click_finish() action.
"""

from components.base_component import BaseComponent
from locators.target.migration_summary_screen import FINISH_LINK_LOCATOR


class MigrationSummaryScreen:
    def __init__(self, app_session):
        self._finish_link = BaseComponent(app_session, *FINISH_LINK_LOCATOR, "FinishLink")

    def click_finish(self) -> None:
        self._finish_link.click()
