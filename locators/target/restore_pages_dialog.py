"""Locators for components.target.browser_sign_in_page.RestorePagesDialog (Chrome's
"Chrome didn't shut down correctly" restore-pages dialog).
"""

# Deliberately scoped to ImageButton specifically -- a bare //*[@Name="Close"] would match
# the window's own WindowsCaptionButton "Close" FIRST (closing the whole browser), since
# find_element returns the first document-order match.
RESTORE_PAGES_CLOSE_BUTTON_LOCATOR = ("xpath", '//ImageButton[@Name="Close"]')
