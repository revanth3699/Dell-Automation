"""Locators for components.target.pairing_code_entry_screen.PairingCodeEntryScreen
("Let's connect your two PCs" -- enter the verification code shown on Source PC).
Confirmed from a user-supplied flow diagram (dell screens flow.pdf, 2026-10-05), not yet
independently confirmed live. The 6 individual code-entry boxes' exact accessible names
are NOT confirmed -- see the component's own docstring for why they're found positionally
instead of by name here.
"""

CONNECT_TWO_PCS_HEADING_LOCATOR = ("xpath", '//*[@Name="Let\'s connect your two PCs"]')
