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
MIGRATION_ERROR_BODY_LOCATOR = ("xpath", '//*[contains(@Name, "Please close and try again")]')
