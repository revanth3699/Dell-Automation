"""Expected heading text + locator + assertion function for
components.target.learn_about_erase_screen.LearnAboutEraseScreen -- the informational
screen reached from the Migration Done screen's "Learn about erase" tile.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/results/LearnAboutEraseView.tsx renders a StageCard titled
t('LearnAboutErase_Title') = "Ready to erase your old PC?" (Resources/Resources.resx).
Apostrophe-free, so matched exactly. Never a click target, so it lives here.
"""

from assertions.common import text_exists

HEADING_TEXT = "Ready to erase your old PC?"
LEARN_ABOUT_ERASE_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, LEARN_ABOUT_ERASE_HEADING_LOCATOR, "LearnAboutEraseHeading", timeout=timeout)
