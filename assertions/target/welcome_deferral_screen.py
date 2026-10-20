"""Expected heading text + locator + assertion function for
components.target.welcome_deferral_screen.WelcomeDeferralScreen -- the "No rush" reminder
picker shown in the Welcome screen's right card after clicking "Remind me later."

Verified against source, not live: rebit TargetPc.UI
web/src/screens/welcome/WelcomeFamilyStage.tsx (ReminderPicker, mode 'picker') renders an
<h2> with t('WelcomeDeferral_PickerTitle') = "No rush—we’ll remind you"
(Resources/Resources.resx). That string has both an em dash and a curly apostrophe, so
this matches the short leading substring "No rush" via contains(). Never a click target,
so it lives here.
"""

from assertions.common import text_exists

HEADING_CONTAINS_TEXT = "No rush"
WELCOME_DEFERRAL_HEADING_LOCATOR = ("xpath", f'//*[contains(@Name, "{HEADING_CONTAINS_TEXT}")]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, WELCOME_DEFERRAL_HEADING_LOCATOR, "WelcomeDeferralHeading", timeout=timeout)
