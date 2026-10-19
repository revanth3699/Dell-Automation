"""Locators for components.target.common_dialogs.TrustNetworkDialog -- click-target
locator only. The heading assertion locator lives in
assertions/target/trust_network_dialog.py instead.
"""

TRUST_NETWORK_BUTTON_LOCATOR = ("xpath", '//*[@Name="Trust network"]')

# Added 2026-10-19 (verified against rebit source, not live): TrustNetworkModel.tsx's
# PopUpModelFooter secondaryLabel is Buttons_Cancel ("Cancel"), a DDSButton.
CANCEL_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Cancel"]')
