"""Expected heading text + locator + assertion function for
components.target.ready_to_move_screen.ReadyToMoveScreen -- the "We're preparing the
files and settings on your old PC" wait screen shown right after pairing, while the
engine runs Compatibility.Migration / MigrationInfo.Init.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/migration-setup/ReadyToMoveStage.tsx renders a StageCard whose title is
t('ReadyToMove_Title') = "We’re preparing the files and settings on your old PC"
(Resources/Resources.resx). The real string has a CURLY apostrophe in "We’re", so this
matches on an apostrophe-free substring via contains() rather than the exact text.
Never a click target, so it lives here rather than in locators/.
"""

from assertions.common import text_exists

HEADING_CONTAINS_TEXT = "preparing the files and settings"
READY_TO_MOVE_HEADING_LOCATOR = ("xpath", f'//*[contains(@Name, "{HEADING_CONTAINS_TEXT}")]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, READY_TO_MOVE_HEADING_LOCATOR, "ReadyToMoveHeading", timeout=timeout)
