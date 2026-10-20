"""Locators for components.target.deferral_success_screen.DeferralSuccessScreen --
click-target locator only. The heading assertion locator lives in
assertions/target/deferral_success_screen.py instead.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/welcome/WelcomeFamilyStage.tsx (ReminderSuccess) renders the same plain
<button> labelled t('Buttons_Close') = "Close" (+ aria-hidden close-x icon) as the
reminder picker, so the locator is shared from locators/target/welcome_deferral_screen.py
rather than duplicated (title-bar CloseButton excluded there).
"""

from locators.target.welcome_deferral_screen import CLOSE_BUTTON_LOCATOR

__all__ = ["CLOSE_BUTTON_LOCATOR"]
