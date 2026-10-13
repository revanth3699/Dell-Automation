"""Expected heading text + locator + assertion function for
components.target.migration_summary_screen.MigrationSummaryScreen -- shown once the
transfer finishes. Confirmed from a user-supplied screenshot (2026-10-06): "Here's a
summary of your migration results". Never a click target, so it lives here rather than
in locators/ -- per explicit user direction (2026-10-14).

This confirmed, literally-visible heading text (corrected 2026-10-06 per direct user
clarification) -- an earlier version used "We have successfully migrated your files",
which was never actually seen in the supplied screenshot and has been replaced.
"""

from assertions.common import text_exists

HEADING_TEXT = "Here's a summary of your migration results"
MIGRATION_SUCCESS_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, MIGRATION_SUCCESS_HEADING_LOCATOR, "MigrationSuccessHeading", timeout=timeout)
