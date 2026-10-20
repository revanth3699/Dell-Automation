"""Expected heading text + locator + assertion function for the Sign-In modal's
"launching" view -- shown once browser sign-in has succeeded and the engine
(DellDataManager) is being launched. Pure check: the view has no footer buttons and no
dismiss path (SignInModal.tsx renders actions={<></>} and no onDismiss), so there is no
components/ class for it -- flows call is_showing() directly.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/onboarding/SignInModal.tsx (state.isLaunching branch) renders a
PopUpModel titled t('SignIn_LaunchingTitle') = "We’re getting your account ready"
(Resources/Resources.resx). Curly apostrophe in "We’re", so this matches the
apostrophe-free substring via contains().
"""

from assertions.common import text_exists

HEADING_CONTAINS_TEXT = "getting your account ready"
SIGN_IN_LAUNCHING_HEADING_LOCATOR = ("xpath", f'//*[contains(@Name, "{HEADING_CONTAINS_TEXT}")]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, SIGN_IN_LAUNCHING_HEADING_LOCATOR, "SignInLaunchingHeading", timeout=timeout)
