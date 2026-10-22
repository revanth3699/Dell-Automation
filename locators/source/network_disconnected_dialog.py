"""Locators for components.source.network_disconnected_dialog.NetworkDisconnectedDialog
-- click-target locator only. The heading assertion locator lives in
assertions/source/network_disconnected_dialog.py instead.

2026-10-19, verified against rebit source (not live): "Check again" exists nowhere in
MigrateToDell.UI -- every Source no-network screen (Controls/NetworkDisconnected.xaml,
Views/FailurePage.xaml NetworkThisPCSection) has only a CancelControl ("Cancel",
resx CancelText), and the HelloPage variant has no button at all and re-runs the
precheck itself when the network returns. The former CHECK_AGAIN_BUTTON_LOCATOR was
removed on 2026-10-22 once flows/source/pairing_flow.py stopped clicking it (nothing
references it now); Cancel is the only click target, used by the state-machine model.
"""

CANCEL_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Cancel"]')
