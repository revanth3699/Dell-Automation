"""Locators for components.target.no_device_found_modal.NoDeviceFoundModal -- click-target
locator only. The heading assertion locator lives in
assertions/target/no_device_found_modal.py instead.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/migration-setup/NoDeviceFoundModal.tsx renders a single-button
PopUpModelFooter whose primary DDSButton is t('Buttons_CancelTransfer') = "Cancel
transfer" (Resources/Resources.resx). Same accessible Name as the Cancel transfer
buttons on NetworkDisconnectedDialog / OtherPcNetworkDisconnectedDialog /
PlugIntoAcPowerDialog -- callers must check this modal's own heading first.
"""

CANCEL_TRANSFER_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Cancel transfer"]')
