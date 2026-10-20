"""Locators for components.target.not_admin_dialog.NotAdminDialog -- click-target locator
only. The heading assertion locator lives in assertions/target/not_admin_dialog.py
instead.

Verified against source, not live: rebit TargetPc.UI web/src/App.tsx mounts
FatalPrecheckModel for the 'notAdmin' overlay with closeLabelKey="Buttons_CancelTransfer",
so screens/precheck/FatalPrecheckModel.tsx's single PopUpModelFooter DDSButton reads
t('Buttons_CancelTransfer') = "Cancel transfer" (Resources/Resources.resx) rather than
the component's default "Close". Clicking it navigates back to Welcome
(NotAdminPageViewModel.ExecuteClose) instead of closing the app.
"""

CANCEL_TRANSFER_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Cancel transfer"]')
