"""Expected body text + locator + assertion function for
components.target.feedback_modal.FeedbackModal -- the "Tell us how we did" popup opened
from the Migration Done screen's tile of the same name.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/results/FeedbackModal.tsx renders a PopUpModel titled
t('MigrationDone_TellUsHowWeDid') -- the SAME string as the tile that opens it
(screens/results/MigrationDoneView.tsx), so the title cannot distinguish "modal open"
from "tile visible". This asserts on the modal's body text instead:
t('MigrationDone_FeedbackBody') = "We’d like to hear about your experience with Dell
Migrate." (Resources/Resources.resx). Curly apostrophe in "We’d", so it matches the
apostrophe-free substring via contains(). Never a click target, so it lives here.
"""

from assertions.common import text_exists

BODY_CONTAINS_TEXT = "hear about your experience"
FEEDBACK_BODY_LOCATOR = ("xpath", f'//*[contains(@Name, "{BODY_CONTAINS_TEXT}")]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, FEEDBACK_BODY_LOCATOR, "FeedbackBody", timeout=timeout)
