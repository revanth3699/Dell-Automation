"""Locators for components.target.common_dialogs.DesktopShortcutDialog -- click-target
locator only. The heading assertion locator lives in
assertions/target/desktop_shortcut_dialog.py instead. Has "No, thanks" and "Create
shortcut" buttons.
"""

CREATE_SHORTCUT_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Create shortcut"]')

# Added 2026-10-19 (verified against rebit source, not live): DesktopShortcutModal.tsx's
# PopUpModelFooter secondaryLabel is Buttons_NoThanks ("No, thanks"), a DDSButton.
NO_THANKS_BUTTON_LOCATOR = ("xpath", '//Button[@Name="No, thanks"]')
