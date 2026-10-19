"""Locators for components.target.common_dialogs.SignInWaitingModal -- click-target
locator only. The heading assertion locator lives in
assertions/target/sign_in_waiting_modal.py instead. The Cancel button's exact
accessible name is NOT yet confirmed live -- inferred from its visible label only.
"""

SIGN_IN_WAITING_CANCEL_BUTTON_LOCATOR = ("xpath", '//*[@Name="Cancel"]')

# Added 2026-10-19 (verified against rebit source, not live): SignInModal.tsx's waiting
# view has an inline <button className=link> labelled SignIn_RetryLink ("Retry") that
# re-opens the browser sign-in. //* rather than //Button since it is link-styled (same
# convention as the Cancel locator above). Note "Retry" is also the DDSButton label on
# SignInFailedDialog (Buttons_Retry) -- callers gate on this modal's is_showing() first.
RETRY_LINK_LOCATOR = ("xpath", '//*[@Name="Retry"]')
