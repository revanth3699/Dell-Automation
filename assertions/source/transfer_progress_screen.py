"""Expected text + locators + assertion functions for
components.source.transfer_progress_screen -- the post-pairing transfer-start sequence
on Source PC: "We've successfully linked your PCs." (a brief confirmation, not
confirmed to always appear) -> "Are you ready to start your migration?" -> "We're
migrating your data now." -> one of two final screens, confirmed via two user-supplied
screenshots (2026-10-14):

  - "We've completed your migration." -- full success, body "Great job! You've
    successfully migrated your data to your new PC. Check to make sure everything is
    there, and when you're ready, Erase this PC."
  - "Your migration summary is ready." -- partial migration (some data was skipped),
    body "We weren't able to move all your data. To see what didn't make it, select
    Show skipped files on your other PC. When you're ready to try again, select Retry,
    or Finish to continue without the skipped data."

Both have their own "Close" button (same accessible name on both screens -- see
locators/source/transfer_progress_screen.py's single shared CLOSE_BUTTON_LOCATOR). Which
one actually appears is the real migration outcome (full vs partial), so
flows/source/transfer_flow.py races both rather than assuming one.

Bug fixed here, confirmed directly by the user via two live runs: an EARLIER version of
this file assumed "Your migration summary is ready." was the one unconditional final
screen for every run, with body "Check your other PC for a summary of what was moved" --
that body text was never actually confirmed live and the heading-only screen this file
tried to detect genuinely never appeared in a full-success run (it only polled this one
heading and timed out indefinitely against a live "We've completed your migration."
screen it had no check for at all). Replaced with the two real, confirmed, mutually
exclusive screens above. None of the locators below are ever click targets (other than
the shared Close button, which lives in locators/ instead), so they live here rather
than in locators/ -- per explicit user direction (2026-10-14).
"""

from assertions.common import all_exist, text_exists

LINKED_SUCCESS_HEADING_TEXT = "We've successfully linked your PCs."
READY_TO_MIGRATE_HEADING_TEXT = "Are you ready to start your migration?"
MIGRATING_DATA_HEADING_TEXT = "We're migrating your data now."
MIGRATION_COMPLETE_HEADING_TEXT = "We've completed your migration."
# Apostrophe-free substring of "Great job! You've successfully migrated your data to
# your new PC. Check to make sure everything is there, and when you're ready, Erase
# this PC." -- avoids the exact-match apostrophe-mismatch trap already hit once this
# project (see assertions/target/sign_in_failed_dialog.py's own history).
MIGRATION_COMPLETE_BODY_CONTAINS_TEXT = "Check to make sure everything is there"
MIGRATION_SUMMARY_READY_HEADING_TEXT = "Your migration summary is ready."
# Confirmed via a user-supplied screenshot (2026-10-14): the real body text for the
# PARTIAL-migration variant of this heading (supersedes an earlier, never-confirmed
# guess -- see module docstring). Apostrophe-free substring, same reasoning as above.
MIGRATION_SUMMARY_BODY_CONTAINS_TEXT = "weren't able to move all your data"

LINKED_SUCCESS_HEADING_LOCATOR = ("xpath", f'//*[@Name="{LINKED_SUCCESS_HEADING_TEXT}"]')
READY_TO_MIGRATE_HEADING_LOCATOR = ("xpath", f'//*[@Name="{READY_TO_MIGRATE_HEADING_TEXT}"]')
MIGRATING_DATA_HEADING_LOCATOR = ("xpath", f'//*[@Name="{MIGRATING_DATA_HEADING_TEXT}"]')
MIGRATION_COMPLETE_HEADING_LOCATOR = ("xpath", f'//*[@Name="{MIGRATION_COMPLETE_HEADING_TEXT}"]')
MIGRATION_COMPLETE_BODY_LOCATOR = (
    "xpath",
    f'//*[contains(@Name, "{MIGRATION_COMPLETE_BODY_CONTAINS_TEXT}")]',
)
MIGRATION_SUMMARY_READY_HEADING_LOCATOR = ("xpath", f'//*[@Name="{MIGRATION_SUMMARY_READY_HEADING_TEXT}"]')
MIGRATION_SUMMARY_BODY_LOCATOR = (
    "xpath",
    f'//*[contains(@Name, "{MIGRATION_SUMMARY_BODY_CONTAINS_TEXT}")]',
)


def is_linked_success(session, timeout: float = 2.0) -> bool:
    return text_exists(session, LINKED_SUCCESS_HEADING_LOCATOR, "LinkedSuccessHeading", timeout=timeout)


def is_ready_to_migrate(session, timeout: float = 2.0) -> bool:
    return text_exists(session, READY_TO_MIGRATE_HEADING_LOCATOR, "ReadyToMigrateHeading", timeout=timeout)


def is_migrating(session, timeout: float = 2.0) -> bool:
    return text_exists(session, MIGRATING_DATA_HEADING_LOCATOR, "MigratingDataHeading", timeout=timeout)


def is_migration_complete_confirmed(session, timeout: float = 2.0) -> bool:
    """Full-success final screen: "We've completed your migration." Requires both the
    heading AND the body text underneath it, same two-texts pattern as
    is_summary_confirmed() below."""
    return all_exist(
        session,
        [
            (MIGRATION_COMPLETE_HEADING_LOCATOR, "MigrationCompleteHeading"),
            (MIGRATION_COMPLETE_BODY_LOCATOR, "MigrationCompleteBody"),
        ],
        timeout=timeout,
    )


def is_summary_confirmed(session, timeout: float = 2.0) -> bool:
    """Partial-migration final screen: "Your migration summary is ready." (some data
    was skipped). Requires both the heading AND the body text underneath it -- require
    both, not just the heading."""
    return all_exist(
        session,
        [
            (MIGRATION_SUMMARY_READY_HEADING_LOCATOR, "MigrationSummaryReadyHeading"),
            (MIGRATION_SUMMARY_BODY_LOCATOR, "MigrationSummaryBody"),
        ],
        timeout=timeout,
    )
