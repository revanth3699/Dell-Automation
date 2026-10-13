"""Expected heading/body text + heading locator + assertion function for
components.target.common_dialogs.MigrationErrorDialog ("Something went wrong" -- a
fatal engine-side error during Target migration prep/transfer, e.g. "error 2969").
Confirmed from a user-supplied screenshot (2026-10-08). Also confirmed from a raw
TargetPc log excerpt the same day: "Engine reported error 2969 on MigrationStatus
(Status=false) after pairing -> FailurePage... Showing React overlay 'failure'".

The heading is never a click target (no accept()/close() for this dialog -- it's a
terminal failure, read_error_text() just reads the body for diagnostics), so it lives
here rather than in locators/ -- per explicit user direction (2026-10-14). The body
locator stays in locators/target/migration_error_dialog.py since it's read via
get_text() by the component's own action, not checked for existence here.
"""

from assertions.common import text_exists

HEADING_TEXT = "Something went wrong"

# Flagged via code review (2026-10-09): this matches on the dialog's generic trailing
# instruction, not something structurally tied to the dialog itself -- a brittleness
# tradeoff accepted deliberately rather than guessed around. The actual UIA tree for
# this dialog hasn't been inspected live (no hardware access when this was reviewed),
# so a "more structural" locator (e.g. relative to the heading's container) would be an
# unverified guess, which risks replacing a confirmed-working locator with a worse one.
# If a future copy change breaks this, MigrationErrorDialog.read_error_text()'s
# except-fallback ("(error text unavailable)") degrades gracefully rather than
# crashing -- is_showing() (keyed on the stable heading above) is unaffected either way.
BODY_CONTAINS_TEXT = "Please close and try again"

MIGRATION_ERROR_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(session, MIGRATION_ERROR_HEADING_LOCATOR, "MigrationErrorHeading", timeout=timeout)
