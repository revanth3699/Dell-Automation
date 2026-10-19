"""Target-role "We're preparing the files and settings on your old PC" screen
(ReadyToMoveStage). Its only user action is the StageCard's top-right Cancel link,
which abandons the migration and exits the app (per the comment in
ReadyToMoveStage.tsx). See assertions/target/ready_to_move_screen.py's is_showing().

Verified against source, not live: rebit TargetPc.UI
web/src/screens/migration-setup/ReadyToMoveStage.tsx + components/stage/StageCard.tsx,
resx key Buttons_Cancel.
"""

from components.base_component import BaseComponent
from locators.target.ready_to_move_screen import CANCEL_BUTTON_LOCATOR


class ReadyToMoveScreen:
    def __init__(self, app_session):
        self._cancel_button = BaseComponent(app_session, *CANCEL_BUTTON_LOCATOR, "ReadyToMoveCancelButton")

    def click_cancel(self) -> None:
        self._cancel_button.click()
