"""Locators for components.source.transfer_progress_screen -- click-target locator
only. Every heading/body assertion locator for this screen family lives in
assertions/source/transfer_progress_screen.py instead (never click targets).

Confirmed via two user-supplied screenshots (2026-10-14): both final screens --
"We've completed your migration." (full success) and "Your migration summary is
ready." (partial migration) -- have a button with the identical accessible name
"Close", so one locator covers both.
"""

CLOSE_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Close"]')
