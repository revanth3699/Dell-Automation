"""Expected heading text + locator + assertion functions for the Target
transfer-in-progress screen ("We're moving your files and settings", shown right after
clicking "Migrate now" on "Your files are ready to move"). Confirmed from a
user-supplied screenshot (2026-10-06). Never a click target, so it lives here rather
than in locators/ -- per explicit user direction (2026-10-14). No corresponding
component exists -- this screen has no action of its own, only these checks.
"""

from assertions.common import gone, text_exists

# Updated 2026-10-19 from rebit TargetPc.UI Resources.resx (Migrating_Title): the real heading
# is now "We’re transferring your files and settings" (curly apostrophe), so this matches on an
# apostrophe-free substring instead of the full text.
HEADING_CONTAINS_TEXT = "transferring your files and settings"
MOVING_FILES_HEADING_LOCATOR = ("xpath", f'//*[contains(@Name, "{HEADING_CONTAINS_TEXT}")]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, MOVING_FILES_HEADING_LOCATOR, "MovingFilesHeading", timeout=timeout)


def wait_until_gone(session, timeout: float) -> bool:
    return gone(session, MOVING_FILES_HEADING_LOCATOR, "MovingFilesHeading", timeout=timeout)
