"""Locators for components.target.common_dialogs.PlugIntoAcPowerDialog -- click-target
locator only. The heading assertion locator lives in
assertions/target/plug_into_ac_power_dialog.py instead.

Bug fixed here, confirmed live (2026-10-14) by attaching read-only to a real session
with the dialog actually showing and reading its page source directly: the button's
real accessible name is "Cancel transfer" (same wording as
OtherPcNetworkDisconnectedDialog's own button), not "Cancel" -- the old locator never
matched, which is why click_cancel() always failed/no-opped in every live run that hit
this dialog.
"""

PLUG_INTO_AC_POWER_CANCEL_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Cancel transfer"]')
