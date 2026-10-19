"""Locators for components.target.sign_out_modal.SignOutModal -- click-target locators
only. The heading assertion locators live in assertions/target/sign_out_modal.py instead.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/onboarding/SignOutModal.tsx (Resources/Resources.resx):
- CANCEL_BUTTON_LOCATOR: both views have a PopUpModelFooter DDSButton labelled
  t('Buttons_Cancel') = "Cancel" (the waiting view's only button; the error view's
  secondary button).
- RETRY_BUTTON_LOCATOR: the error view's primary DDSButton, t('Buttons_Retry') =
  "Retry". Not present in the waiting view.
"""

CANCEL_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Cancel"]')
RETRY_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Retry"]')
