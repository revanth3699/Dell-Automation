"""Locators for components.target.welcome_links.WelcomeLinks -- click-target locators
only, for the two secondary links on the Welcome screen's right ("Move my files") card.
Kept separate from locators/target/welcome_screen.py and welcome_back_screen.py (which
are not modified) -- those only hold the arrow Continue button.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/welcome/WelcomeMoveFilesCard.tsx (Resources/Resources.resx):
- REMIND_ME_LATER_BUTTON_LOCATOR: a plain <button> labelled t('Buttons_RemindLater') =
  "Remind me later." -- note the trailing full stop is part of the resx value and so of
  the accessible Name. Rendered only when showRemindLater is true (the migrate variant).
- SIGN_OUT_LINK_LOCATOR: a DDSLink labelled t('Buttons_SignOut') = "Sign out" with a
  leading aria-hidden user-cir icon, rendered only when isSignedIn. A link, hence //*.
  The same XPath already exists as assertions/target/welcome_back_screen.py's
  SIGN_OUT_BUTTON_LOCATOR, used there purely as a presence check; this is the click
  target, so it lives here (dual-purpose element).
"""

REMIND_ME_LATER_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Remind me later."]')
SIGN_OUT_LINK_LOCATOR = ("xpath", '//*[@Name="Sign out"]')
