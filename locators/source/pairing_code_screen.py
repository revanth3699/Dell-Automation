"""Locators for components.source.pairing_code_screen.PairingCodeScreen ("Let's finish
linking your PCs."). Confirmed live (2026-10-06) via Phase 0 spike against the real
Source build -- see tools/_phase0_source_tree_dump_code.xml for the raw capture this was
derived from.

Real app bug, confirmed reproducible across multiple code rotations: the 6-box
ListView ("VerificationListControl") only ever exposes 5 of its 6 digit boxes in the UI
Automation tree at any given snapshot -- WHICH position (AutomationId) is missing shifts
between rotations, not a fixed index. See components/source/pairing_code_screen.py's
PairingCodeScreen.read_code() for the OCR-based workaround. Treat every box locator here
as optional (exists() can legitimately return False for any one of them on any given
read) -- never require all 6 to be present as a precondition for anything.
"""

HEADING_LOCATOR = ("xpath", '//*[@Name="Let\'s finish linking your PCs."]')
CODE_BOX_LOCATORS = [
    ("xpath", f'//*[@AutomationId="VerificationCode_{i}"]') for i in range(6)
]
RETRY_TIME_TEXT_LOCATOR = ("xpath", '//*[@AutomationId="TxtCodeRetryTime"]')
CANCEL_BUTTON_LOCATOR = ("xpath", '//*[@Name="Cancel"]')
