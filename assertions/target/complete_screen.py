"""Expected heading text + locator + assertion function for
components.target.complete_screen.CompleteScreen -- the read-only migration detail
screen reached from the results summary's "View the details" link.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/results/CompleteView.tsx renders a StagePanel titled
t('Complete_Title') = "Your transfer is complete" (Resources/Resources.resx). That is
IDENTICAL to the results-summary heading already asserted by
assertions/target/migration_summary_screen.py, so the heading alone cannot tell the two
screens apart. is_showing() therefore AND-gates the heading with this screen's own
"Back to summary" header link (Complete_BackToSummary) via assertions.common.all_exist.
The link locator is a genuine click target too, so it lives in
locators/target/complete_screen.py and is imported from there.
"""

from assertions.common import all_exist
from locators.target.complete_screen import BACK_TO_SUMMARY_LINK_LOCATOR

HEADING_TEXT = "Your transfer is complete"
COMPLETE_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return all_exist(
        session,
        [
            (COMPLETE_HEADING_LOCATOR, "CompleteHeading"),
            (BACK_TO_SUMMARY_LINK_LOCATOR, "BackToSummaryLink"),
        ],
        timeout=timeout,
    )
