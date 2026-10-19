"""Locators for components.target.connection_lost_dialog.ConnectionLostDialog --
click-target locators only. The heading assertion locator lives in
assertions/target/connection_lost_dialog.py instead.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/precheck/ConnectionLostModal.tsx renders a PopUpModelFooter of two
DDSButtons: secondary t('Buttons_CancelTransfer') = "Cancel transfer" (closes the app)
and primary t('Buttons_TryAgain') = "Try again" (Resources/Resources.resx).
"""

TRY_AGAIN_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Try again"]')
CANCEL_TRANSFER_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Cancel transfer"]')
