"""Expected heading text + locator + assertion function for
components.target.not_admin_dialog.NotAdminDialog -- the dead-end precheck failure shown
when the app is not running with admin rights.

Verified against source, not live: rebit TargetPc.UI. App.tsx renders
screens/precheck/FatalPrecheckModel.tsx for overlay id 'notAdmin'; its PopUpModel title
is the bridge-supplied state.title, which NotAdminPageViewModel.cs's Title property
returns as Resources.NotAdmin_Title = "Admin access is required"
(Resources/Resources.resx). Apostrophe-free, so matched exactly. Never a click target,
so it lives here.
"""

from assertions.common import text_exists

HEADING_TEXT = "Admin access is required"
NOT_ADMIN_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(session, NOT_ADMIN_HEADING_LOCATOR, "NotAdminHeading", timeout=timeout)
