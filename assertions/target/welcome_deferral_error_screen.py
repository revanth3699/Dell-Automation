"""Expected heading text + locator + assertion function for
components.target.welcome_deferral_error_screen.WelcomeDeferralErrorScreen -- the error
card shown in the Welcome screen's right card when scheduling a reminder fails.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/welcome/WelcomeFamilyStage.tsx (ReminderErrorCard, mode 'error') renders
an <h2> with t('WelcomeDeferralError_Title') = "We couldn’t schedule your reminder"
(Resources/Resources.resx). Curly apostrophe in "couldn’t", so this matches the
apostrophe-free substring via contains(). Never a click target, so it lives here.
"""

from assertions.common import text_exists

HEADING_CONTAINS_TEXT = "schedule your reminder"
WELCOME_DEFERRAL_ERROR_HEADING_LOCATOR = ("xpath", f'//*[contains(@Name, "{HEADING_CONTAINS_TEXT}")]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(
        session, WELCOME_DEFERRAL_ERROR_HEADING_LOCATOR, "WelcomeDeferralErrorHeading", timeout=timeout
    )
