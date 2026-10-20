"""Locators for components.source.network_disconnected_dialog.NetworkDisconnectedDialog
-- click-target locator only. The heading assertion locator lives in
assertions/source/network_disconnected_dialog.py instead.
"""

CHECK_AGAIN_BUTTON_LOCATOR = ("xpath", '//*[@Name="Check again"]')
# 2026-10-19, verified against rebit source (not live): "Check again" exists nowhere in
# MigrateToDell.UI -- every Source no-network screen (Controls/NetworkDisconnected.xaml,
# Views/FailurePage.xaml NetworkThisPCSection) has only a CancelControl ("Cancel",
# resx CancelText), and the HelloPage variant has no button at all and re-runs the
# precheck itself when the network returns. The state-machine model uses this one;
# CHECK_AGAIN_BUTTON_LOCATOR is kept only because flows/source/*.py still import it.
CANCEL_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Cancel"]')
