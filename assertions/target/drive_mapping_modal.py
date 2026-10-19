"""Expected heading text + locator + assertion function for
components.target.drive_mapping_modal.DriveMappingModal -- the modal opened by a drive
row's "Change" link on the Choose What to Move screen.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/choose-what-to-move/DriveMappingModal.tsx renders a PopUpModel whose
title is the bridge-supplied state.driveMappingHeading, which is one of
DriveMapping_HeadingSingle = "We found 1 drive on your PCs" or
DriveMapping_HeadingMultiple = "We found multiple drives on your PCs"
(Resources/Resources.resx). Both end in "on your PCs", so that shared substring is
matched via contains(). Never a click target, so it lives here.
"""

from assertions.common import text_exists

HEADING_CONTAINS_TEXT = "on your PCs"
DRIVE_MAPPING_HEADING_LOCATOR = ("xpath", f'//*[contains(@Name, "{HEADING_CONTAINS_TEXT}")]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, DRIVE_MAPPING_HEADING_LOCATOR, "DriveMappingHeading", timeout=timeout)
