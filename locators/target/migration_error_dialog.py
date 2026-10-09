"""Locators for components.target.common_dialogs.MigrationErrorDialog ("Something went
wrong" -- a fatal engine-side error during Target migration prep/transfer, e.g. "error
2969"). Confirmed from a user-supplied screenshot (2026-10-08): heading is always
"Something went wrong" regardless of the specific error code, which appears in the body
text instead ("Something went wrong while getting your PCs ready (error 2969). Please
close and try again."). Also confirmed from a raw TargetPc log excerpt the same day:
"Engine reported error 2969 on MigrationStatus (Status=false) after pairing ->
FailurePage... Showing React overlay 'failure'" -- this is a genuine fatal engine
failure, not a transient UI glitch.
"""

MIGRATION_ERROR_HEADING_LOCATOR = ("xpath", '//*[@Name="Something went wrong"]')

# Flagged via code review (2026-10-09): this matches on the dialog's generic trailing
# instruction, not something structurally tied to the dialog itself -- a brittleness
# tradeoff accepted deliberately rather than guessed around. The actual UIA tree for
# this dialog hasn't been inspected live (no hardware access when this was reviewed),
# so a "more structural" locator (e.g. relative to the heading's container) would be an
# unverified guess, which risks replacing a confirmed-working locator with a worse one.
# If a future copy change breaks this, MigrationErrorDialog.read_error_text()'s
# except-fallback ("(error text unavailable)") degrades gracefully rather than
# crashing -- is_showing() (keyed on the stable heading above) is unaffected either way.
MIGRATION_ERROR_BODY_LOCATOR = ("xpath", '//*[contains(@Name, "Please close and try again")]')
