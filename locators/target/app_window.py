"""Locators for the Target app's own native window chrome (title-bar buttons) --
click-target locator only. AutomationId confirmed live (2026-10-06) via a raw
//Button dump against the real app (see
components/target/transfer_receive_screen.py's own _KNOWN_CHROME_AUTOMATION_IDS,
which excludes this same set of native buttons from that screen's own
"find the real button" diagnostic).
"""

CLOSE_BUTTON_LOCATOR = ("xpath", '//Button[@AutomationId="CloseButton"]')
