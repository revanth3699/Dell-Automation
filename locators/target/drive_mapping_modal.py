"""Locators for components.target.drive_mapping_modal.DriveMappingModal -- click-target
locators only. The heading assertion locator lives in
assertions/target/drive_mapping_modal.py instead.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/choose-what-to-move/DriveMappingModal.tsx. The footer is a
PopUpModelFooter (components/common/PopUpModelFooter.tsx) of two DDSButtons:
secondary t('Buttons_Cancel') = "Cancel" and primary t('Buttons_Apply') = "Apply"
(Resources/Resources.resx). The rescan control is a DDSLink in the body labelled
t('Buttons_RescanForDrives') = "Rescan for connected drives" -- a link, hence //*.
"""

APPLY_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Apply"]')
CANCEL_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Cancel"]')
RESCAN_LINK_LOCATOR = ("xpath", '//*[@Name="Rescan for connected drives"]')
