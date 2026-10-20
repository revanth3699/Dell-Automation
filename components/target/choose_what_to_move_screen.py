"""Target-role "Tell us what you want to transfer" screen (ChooseWhatToMoveStage) --
actions only. Covers both modes' secondary controls: "Let me choose what to transfer"
(everything mode -> tree mode), and the tree mode's Select-all checkbox, "Go back",
per-drive "Change" (opens the Drive Mapping modal -- see
components/target/drive_mapping_modal.py) and the header "Cancel" link. The "Migrate
now" arrow button is deliberately NOT duplicated here -- use
components.target.transfer_receive_screen.TransferReceiveScreen.start_transfer(). See
assertions/target/choose_what_to_move_screen.py for is_showing() and
is_does_not_fit_warning_showing().

Verified against source, not live: rebit TargetPc.UI
web/src/screens/migration-setup/ChooseWhatToMoveStage.tsx,
screens/choose-what-to-move/{ChooseFilesLinkCard,FileSelectionTreeCard,
UserStorageSummaryCard}.tsx, components/stage/StagePanelHeader.tsx; resx keys
ChooseWhatToMove_ChooseCustomCard, Buttons_GoBack, ChooseWhatToMove_SelectAllLabel,
Buttons_Change, Buttons_Cancel. See the locator module for the unverified Select-all
checkbox mapping.
"""

from components.base_component import BaseComponent
from locators.target.choose_what_to_move_screen import (
    CANCEL_LINK_LOCATOR,
    CHANGE_LINK_LOCATOR,
    GO_BACK_LINK_LOCATOR,
    LET_ME_CHOOSE_LINK_LOCATOR,
    SELECT_ALL_CHECKBOX_LOCATOR,
)


class ChooseWhatToMoveScreen:
    def __init__(self, app_session):
        self._let_me_choose_link = BaseComponent(app_session, *LET_ME_CHOOSE_LINK_LOCATOR, "LetMeChooseLink")
        self._go_back_link = BaseComponent(app_session, *GO_BACK_LINK_LOCATOR, "GoBackLink")
        self._select_all_checkbox = BaseComponent(app_session, *SELECT_ALL_CHECKBOX_LOCATOR, "SelectAllCheckbox")
        self._change_link = BaseComponent(app_session, *CHANGE_LINK_LOCATOR, "ChangeDriveLink")
        self._cancel_link = BaseComponent(app_session, *CANCEL_LINK_LOCATOR, "ChooseWhatToMoveCancelLink")

    def click_let_me_choose(self) -> None:
        self._let_me_choose_link.click()

    def click_go_back(self) -> None:
        self._go_back_link.click()

    def click_select_all(self) -> None:
        self._select_all_checkbox.click()

    def click_change_drive(self) -> None:
        self._change_link.click()

    def click_cancel(self) -> None:
        self._cancel_link.click()
