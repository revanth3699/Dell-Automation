"""Locators for components.source.trust_network_dialog.TrustNetworkDialog ("Do you trust
the <network> network?"). Confirmed from a user-supplied screenshot (2026-10-06) -- NOT
yet confirmed live against the real Source build (it didn't appear in the one live run
done so far, likely because it's conditional on network-trust state). Treat as
best-effort until seen live.
"""

HEADING_LOCATOR = ("xpath", '//*[contains(@Name, "Do you trust the")]')
YES_CONTINUE_BUTTON_LOCATOR = ("xpath", '//*[@Name="Yes, continue"]')
CANCEL_BUTTON_LOCATOR = ("xpath", '//*[@Name="Cancel"]')
