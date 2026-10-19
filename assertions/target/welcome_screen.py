"""Assertion function for components.target.sign_in_screen.WelcomeScreen (the initial,
not-yet-signed-in "Welcome to Dell" screen). SIGN_IN_BUTTON_LOCATOR itself stays in
locators/target/welcome_screen.py -- it's a genuine click target (click_sign_in() uses
it directly), not a pure assertion locator -- this just builds the poll+assert check
around it using the common assertions/common.py methods.
"""

from assertions.common import all_exist, button_exists
from locators.target.welcome_screen import SIGN_IN_BUTTON_LOCATOR

# Added 2026-10-19 (verified against rebit source, not live): the Continue button
# (IconButton ariaLabel=Buttons_Continue in WelcomeMoveFilesCard.tsx) also appears on other
# screens, so is_showing() alone cannot tell the welcome states apart. The right-hand card's
# <h2> title differs per state: WelcomeCard.tsx's signed-out shape passes
# Welcome_SignInOrCreateAccountTitle, while WelcomeFamilyStage.tsx's entitled/signed-in shape
# passes WelcomeMoveFilesCard_Title. Each state check ANDs that title with the button.
SIGNED_OUT_TITLE_TEXT = "Sign in or create an account"
ENTITLED_SIGNED_IN_TITLE_TEXT = "Ready to get started?"
SIGNED_OUT_TITLE_LOCATOR = ("xpath", f'//*[@Name="{SIGNED_OUT_TITLE_TEXT}"]')
ENTITLED_SIGNED_IN_TITLE_LOCATOR = ("xpath", f'//*[@Name="{ENTITLED_SIGNED_IN_TITLE_TEXT}"]')


def is_showing(session, timeout: float = 1.0) -> bool:
    return button_exists(session, SIGN_IN_BUTTON_LOCATOR, "SignInButton", timeout=timeout)


def is_signed_out_showing(session, timeout: float = 1.0) -> bool:
    return all_exist(
        session,
        [(SIGN_IN_BUTTON_LOCATOR, "SignInButton"), (SIGNED_OUT_TITLE_LOCATOR, "WelcomeSignedOutTitle")],
        timeout=timeout,
    )


def is_entitled_signed_in_showing(session, timeout: float = 1.0) -> bool:
    return all_exist(
        session,
        [
            (SIGN_IN_BUTTON_LOCATOR, "SignInButton"),
            (ENTITLED_SIGNED_IN_TITLE_LOCATOR, "WelcomeEntitledSignedInTitle"),
        ],
        timeout=timeout,
    )
