"""Locators for components.source.searching_screen.SearchingScreen ("We're searching for
your new PC."). Confirmed live (2026-10-06): shown after "Let's get started" (and, when
present, after accepting the trust-network dialog), and stays showing until a real Target
PC becomes discoverable on the network -- it does NOT advance on its own after a fixed
timeout, confirmed by waiting 15s+ with no change.
"""

HEADING_LOCATOR = ("xpath", '//*[@AutomationId="TxtProgressPageTitle"][@Name="We\'re searching for your new PC."]')
CANCEL_BUTTON_LOCATOR = ("xpath", '//*[@Name="Cancel"]')
