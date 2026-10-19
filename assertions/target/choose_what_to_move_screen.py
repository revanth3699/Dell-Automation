"""Expected heading/body text + locators + assertion functions for
components.target.choose_what_to_move_screen.ChooseWhatToMoveScreen in its tree
("Let me choose") mode.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/migration-setup/ChooseWhatToMoveStage.tsx renders a StagePanel whose
title is t('ChooseWhatToMove_Title') = "Tell us what you want to transfer" when
state.moveEverything is false (the "everything" mode uses ChooseWhatToMove_Summary_Title
instead -- that heading is already covered by
assertions/target/transfer_receive_screen.py). The does-not-fit warning is
t('ChooseWhatToMove_DriveDoesNotFitWarning') = "You’ll need to free up {0} to continue."
(Resources/Resources.resx), rendered by screens/choose-what-to-move/MigrateNowCard.tsx
as a role="alert" paragraph when any drive row is over capacity. That string has a curly
apostrophe and a runtime size substitution, so it is matched on the apostrophe-free
substring "free up". Neither is ever a click target, so both live here.
"""

from assertions.common import text_exists

HEADING_TEXT = "Tell us what you want to transfer"
CHOOSE_WHAT_TO_MOVE_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')

DOES_NOT_FIT_WARNING_CONTAINS_TEXT = "free up"
DOES_NOT_FIT_WARNING_LOCATOR = ("xpath", f'//*[contains(@Name, "{DOES_NOT_FIT_WARNING_CONTAINS_TEXT}")]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, CHOOSE_WHAT_TO_MOVE_HEADING_LOCATOR, "ChooseWhatToMoveHeading", timeout=timeout)


def is_does_not_fit_warning_showing(session, timeout: float = 1.0) -> bool:
    return text_exists(session, DOES_NOT_FIT_WARNING_LOCATOR, "DriveDoesNotFitWarning", timeout=timeout)
