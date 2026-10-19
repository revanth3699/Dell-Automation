"""Target-role Drive Mapping modal ("We found 1 drive / multiple drives on your PCs"),
opened from the Choose What to Move screen's per-drive "Change" link -- actions only.
See assertions/target/drive_mapping_modal.py's is_showing(). The per-row checkboxes and
destination dropdowns are not modelled here.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/choose-what-to-move/DriveMappingModal.tsx; resx keys Buttons_Apply,
Buttons_Cancel, Buttons_RescanForDrives.
"""

from components.base_component import BaseComponent
from locators.target.drive_mapping_modal import (
    APPLY_BUTTON_LOCATOR,
    CANCEL_BUTTON_LOCATOR,
    RESCAN_LINK_LOCATOR,
)


class DriveMappingModal:
    def __init__(self, app_session):
        self._apply_button = BaseComponent(app_session, *APPLY_BUTTON_LOCATOR, "DriveMappingApplyButton")
        self._cancel_button = BaseComponent(app_session, *CANCEL_BUTTON_LOCATOR, "DriveMappingCancelButton")
        self._rescan_link = BaseComponent(app_session, *RESCAN_LINK_LOCATOR, "DriveMappingRescanLink")

    def click_apply(self) -> None:
        self._apply_button.click()

    def click_cancel(self) -> None:
        self._cancel_button.click()

    def click_rescan(self) -> None:
        self._rescan_link.click()
