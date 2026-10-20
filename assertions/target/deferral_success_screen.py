"""Expected heading text + locator + assertion function for
components.target.deferral_success_screen.DeferralSuccessScreen -- the "Got it"
confirmation shown in the Welcome screen's right card after a reminder is set.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/welcome/WelcomeFamilyStage.tsx (ReminderSuccess, mode 'success') renders
an <h2> with t('WelcomeDeferralSuccess_Title') = "Got it" (Resources/Resources.resx).
Matched exactly -- deliberately NOT contains(), since "Got it" is short enough to be a
substring of unrelated text. Never a click target, so it lives here.
"""

from assertions.common import text_exists

HEADING_TEXT = "Got it"
DEFERRAL_SUCCESS_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, DEFERRAL_SUCCESS_HEADING_LOCATOR, "DeferralSuccessHeading", timeout=timeout)
