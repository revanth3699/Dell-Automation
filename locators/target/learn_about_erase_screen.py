"""Locators for components.target.learn_about_erase_screen.LearnAboutEraseScreen --
click-target locator only. The heading assertion locator lives in
assertions/target/learn_about_erase_screen.py instead.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/results/LearnAboutEraseView.tsx passes cancelLabel=t('Buttons_BackToHome')
= "Back to Home" (Resources/Resources.resx) and showCancelIcon={false} to StageCard, so
components/stage/StageCard.tsx renders a plain <button> whose accessible Name is exactly
"Back to Home". The "Learn more online" DDSButton and "Terms and conditions" DDSLink open
the external browser and are deliberately not modelled.
"""

BACK_TO_HOME_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Back to Home"]')
