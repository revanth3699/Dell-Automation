"""Locators for components.source.trust_network_dialog.TrustNetworkDialog ("Do you trust
the <network> network?"). Confirmed live (2026-10-07): heading text and the "Yes,
continue" button both match a real run's screenshot exactly, including appearing layered
over the pairing-code screen itself (see flows/source/pairing_flow.py's docstring).
"""

HEADING_LOCATOR = ("xpath", '//*[contains(@Name, "Do you trust the")]')
YES_CONTINUE_BUTTON_LOCATOR = ("xpath", '//*[@Name="Yes, continue"]')
CANCEL_BUTTON_LOCATOR = ("xpath", '//*[@Name="Cancel"]')
