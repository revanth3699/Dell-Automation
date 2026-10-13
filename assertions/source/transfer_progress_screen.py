"""Expected text + locators + assertion functions for
components.source.transfer_progress_screen -- the post-pairing transfer-start sequence
on Source PC: "We've successfully linked your PCs." (a brief confirmation, not
confirmed to always appear) -> "Are you ready to start your migration?" -> "We're
migrating your data now." -> one of THREE final screens plus one recoverable error
screen, confirmed via user-supplied screenshots (2026-10-13):

  - "We've completed your migration." -- full success, body "Great job! You've
    successfully migrated your data to your new PC. Check to make sure everything is
    there, and when you're ready, Erase this PC." Has a "Close" button.
  - "Your migration is now complete." -- partial migration (some data was skipped),
    body "We weren't able to move all your data. Click Try Again if you'd like to
    start over. You can also run Dell Data Assistant from your desktop shortcut on
    this PC when you're ready to try again." Has a "Try Again" button, NOT a "Close"
    button -- the only way to dismiss this screen is the close icon (top-right X), see
    locators/source/transfer_progress_screen.py's CLOSE_ICON_LOCATOR.
  - "Your migration summary is ready." -- ALSO a partial-migration final screen (some
    data was skipped), body "We weren't able to move all your data. To see what didn't
    make it, select Show skipped files on your other PC. When you're ready to try
    again, select Retry, or Finish to continue without the skipped data." Has a
    "Close" button (same accessible name as the full-success screen's), unlike "Your
    migration is now complete." above.
  - "We ran into a problem during your migration." -- NOT a final outcome, a
    recoverable error (red icon), body "Try Again now, or wait and run Dell Data
    Assistant from the desktop shortcut on this PC when you're ready." Has its own
    "Try Again" button that restarts the migration -- raced continuously alongside the
    three final screens (per this project's "race it continuously" pattern, see
    CLAUDE.md) rather than treated as an end state.

Bug fixed here, confirmed directly by the user via TWO separate live runs (2026-10-13):
this screen family has now flip-flopped three times between "Your migration is now
complete." and "Your migration summary is ready." as THE partial-migration final
screen -- each live run previously treated whichever heading it had just confirmed
live as the one true partial screen and dropped the other entirely, so the dropped one
then caused the exact same indefinite-polling bug in the next run that showed it
instead. The most recent run's own debug log proves both are real: "Your migration is
now complete." matched heading+body for ~15s, then disappeared, and the screen that
was actually left on screen (confirmed via a live screenshot) was "Your migration
summary is ready." -- a heading this file had stopped checking for after the PREVIOUS
fix. Resolution: stop betting on one -- both are now raced every cycle as alternative
partial-migration outcomes, each with its own heading+body pair and its own dismissal
button (see is_migration_partial_try_again_confirmed() /
is_migration_partial_summary_confirmed() below), the same "race it, don't assume"
pattern this project already uses for the error screen and for every other
unpredictable dialog.

Also fixed in this pass: the previous MIGRATION_PARTIAL_BODY_CONTAINS_TEXT
("weren't able to move all your data") was labeled "apostrophe-free" but was not --
it contained the apostrophe in "weren't", reintroducing the exact
curly-vs-straight-apostrophe trap this project has already been bitten by elsewhere
(see assertions/target/sign_in_failed_dialog.py's history). Both body substrings below
are genuinely apostrophe-free, and each is also now distinctive to its own screen
rather than a prefix the two partial screens happen to share.

Heading/body assertion locators for this screen family live here rather than in
locators/ (never click targets) -- per explicit user direction (2026-10-14). The
close icon and the "Try Again" buttons ARE click targets, so they live in locators/
instead.
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
# Confirmed via a user-supplied screenshot (2026-10-13): one of two partial-migration
# final screens -- has a "Try Again" button, dismissed via the close icon instead (see
# module docstring).
MIGRATION_PARTIAL_TRY_AGAIN_HEADING_TEXT = "Your migration is now complete."
# Apostrophe-free substring distinctive to THIS screen's body (not the shared "We
# weren't able to move all your data." prefix both partial screens start with).
MIGRATION_PARTIAL_TRY_AGAIN_BODY_CONTAINS_TEXT = "Click Try Again if you"
# Confirmed via a user-supplied screenshot (2026-10-13): the OTHER partial-migration
# final screen -- has a "Close" button, same accessible name as the full-success
# screen's (see module docstring).
MIGRATION_PARTIAL_SUMMARY_HEADING_TEXT = "Your migration summary is ready."
# Apostrophe-free substring distinctive to THIS screen's body.
MIGRATION_PARTIAL_SUMMARY_BODY_CONTAINS_TEXT = "select Show skipped files"
# Confirmed via a user-supplied screenshot (2026-10-13): the recoverable migration
# error screen -- NOT a final outcome, see module docstring.
MIGRATION_ERROR_HEADING_TEXT = "We ran into a problem during your migration."
# Apostrophe-free substring of "Try Again now, or wait and run Dell Data Assistant
# from the desktop shortcut on this PC when you're ready." Same reasoning as above.
MIGRATION_ERROR_BODY_CONTAINS_TEXT = "now, or wait and run Dell Data Assistant from the desktop shortcut"

LINKED_SUCCESS_HEADING_LOCATOR = ("xpath", f'//*[@Name="{LINKED_SUCCESS_HEADING_TEXT}"]')
READY_TO_MIGRATE_HEADING_LOCATOR = ("xpath", f'//*[@Name="{READY_TO_MIGRATE_HEADING_TEXT}"]')
MIGRATING_DATA_HEADING_LOCATOR = ("xpath", f'//*[@Name="{MIGRATING_DATA_HEADING_TEXT}"]')
MIGRATION_COMPLETE_HEADING_LOCATOR = ("xpath", f'//*[@Name="{MIGRATION_COMPLETE_HEADING_TEXT}"]')
MIGRATION_COMPLETE_BODY_LOCATOR = (
    "xpath",
    f'//*[contains(@Name, "{MIGRATION_COMPLETE_BODY_CONTAINS_TEXT}")]',
)
MIGRATION_PARTIAL_TRY_AGAIN_HEADING_LOCATOR = (
    "xpath",
    f'//*[@Name="{MIGRATION_PARTIAL_TRY_AGAIN_HEADING_TEXT}"]',
)
MIGRATION_PARTIAL_TRY_AGAIN_BODY_LOCATOR = (
    "xpath",
    f'//*[contains(@Name, "{MIGRATION_PARTIAL_TRY_AGAIN_BODY_CONTAINS_TEXT}")]',
)
MIGRATION_PARTIAL_SUMMARY_HEADING_LOCATOR = (
    "xpath",
    f'//*[@Name="{MIGRATION_PARTIAL_SUMMARY_HEADING_TEXT}"]',
)
MIGRATION_PARTIAL_SUMMARY_BODY_LOCATOR = (
    "xpath",
    f'//*[contains(@Name, "{MIGRATION_PARTIAL_SUMMARY_BODY_CONTAINS_TEXT}")]',
)
MIGRATION_ERROR_HEADING_LOCATOR = ("xpath", f'//*[@Name="{MIGRATION_ERROR_HEADING_TEXT}"]')
MIGRATION_ERROR_BODY_LOCATOR = (
    "xpath",
    f'//*[contains(@Name, "{MIGRATION_ERROR_BODY_CONTAINS_TEXT}")]',
)


def is_linked_success(session, timeout: float = 2.0) -> bool:
    return text_exists(session, LINKED_SUCCESS_HEADING_LOCATOR, "LinkedSuccessHeading", timeout=timeout)


def is_ready_to_migrate(session, timeout: float = 2.0) -> bool:
    return text_exists(session, READY_TO_MIGRATE_HEADING_LOCATOR, "ReadyToMigrateHeading", timeout=timeout)


def is_migrating(session, timeout: float = 2.0) -> bool:
    return text_exists(session, MIGRATING_DATA_HEADING_LOCATOR, "MigratingDataHeading", timeout=timeout)


def is_migration_complete_confirmed(session, timeout: float = 2.0) -> bool:
    """Full-success final screen: "We've completed your migration." Requires both the
    heading AND the body text underneath it, same two-texts pattern as the two partial
    checks below."""
    return all_exist(
        session,
        [
            (MIGRATION_COMPLETE_HEADING_LOCATOR, "MigrationCompleteHeading"),
            (MIGRATION_COMPLETE_BODY_LOCATOR, "MigrationCompleteBody"),
        ],
        timeout=timeout,
    )


def is_migration_partial_try_again_confirmed(session, timeout: float = 2.0) -> bool:
    """One of two partial-migration final screens: "Your migration is now complete."
    (some data was skipped, despite the heading's wording). Has a "Try Again" button,
    NOT a "Close" button -- dismissed via the close icon instead (see module
    docstring). Requires both the heading AND the body text underneath it."""
    return all_exist(
        session,
        [
            (MIGRATION_PARTIAL_TRY_AGAIN_HEADING_LOCATOR, "MigrationPartialTryAgainHeading"),
            (MIGRATION_PARTIAL_TRY_AGAIN_BODY_LOCATOR, "MigrationPartialTryAgainBody"),
        ],
        timeout=timeout,
    )


def is_migration_partial_summary_confirmed(session, timeout: float = 2.0) -> bool:
    """The OTHER partial-migration final screen: "Your migration summary is ready."
    Has a "Close" button (same accessible name as the full-success screen's). Requires
    both the heading AND the body text underneath it."""
    return all_exist(
        session,
        [
            (MIGRATION_PARTIAL_SUMMARY_HEADING_LOCATOR, "MigrationPartialSummaryHeading"),
            (MIGRATION_PARTIAL_SUMMARY_BODY_LOCATOR, "MigrationPartialSummaryBody"),
        ],
        timeout=timeout,
    )


def is_migration_error_confirmed(session, timeout: float = 2.0) -> bool:
    """Recoverable migration error screen: "We ran into a problem during your
    migration." NOT a final outcome -- its "Try Again" button restarts the migration,
    so this is raced continuously alongside the two final screens rather than treated
    as an end state (see module docstring). Requires both the heading AND the body
    text underneath it, same two-texts pattern as the other checks in this file."""
    return all_exist(
        session,
        [
            (MIGRATION_ERROR_HEADING_LOCATOR, "MigrationErrorHeading"),
            (MIGRATION_ERROR_BODY_LOCATOR, "MigrationErrorBody"),
        ],
        timeout=timeout,
    )
