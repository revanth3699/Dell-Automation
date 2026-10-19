"""Expected heading text + locator + assertion function for
components.target.migration_complete_screen.MigrationCompleteScreen -- shown after
clicking "Finish" on MigrationSummaryScreen. Confirmed directly by the user (2026-10-09)
via a live screenshot: "Your migration is now complete". Never a click target, so it
lives here rather than in locators/ -- per explicit user direction (2026-10-14).

Bug fixed here, confirmed directly by the user (2026-10-09): the heading previously on
record here, "We've successfully migrated your files", was never actually seen live --
this is the real heading for this screen.
"""

from assertions.common import text_exists

HEADING_TEXT = "Your transfer is now complete"
MIGRATION_COMPLETE_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, MIGRATION_COMPLETE_HEADING_LOCATOR, "MigrationCompleteHeading", timeout=timeout)
