"""Locators for components.source.confirm_cancel_dialog.ConfirmCancelDialog --
click-target locator only. The heading/body assertion locator lives in
assertions/source/confirm_cancel_dialog.py instead (never a click target).

Confirmed via a user-supplied screenshot (2026-10-13): the dialog has two buttons,
"Yes, cancel now" and "No, don't cancel" -- only the latter is ever clicked by this
project (see assertions/source/confirm_cancel_dialog.py's own docstring for why).
Matched via contains() on an apostrophe-free substring ("No, don") rather than an
exact @Name="No, don't cancel" match, same reasoning as every heading/body text match
in this project -- avoids the curly-vs-straight-apostrophe trap in "don't".
"""

NO_DONT_CANCEL_BUTTON_LOCATOR = ("xpath", '//Button[contains(@Name, "No, don")]')
