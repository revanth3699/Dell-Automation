"""Expected heading text + locator + assertion function for
components.target.common_dialogs.CloseAppsDialog ("We need to close all other
applications"). Confirmed from a user-supplied screenshot (2026-10-06). Never a click
target, so it lives here rather than in locators/ -- per explicit user direction
(2026-10-14).
"""

from assertions.common import text_exists

# Updated 2026-10-19 from rebit TargetPc.UI Resources.resx: the first prompt is
# CloseApplications_Title, and the retry prompt after a failed close is CloseApplications_ErrorTitle.
HEADING_TEXT = "Close other applications"
ERROR_HEADING_TEXT = "Close all other applications"
CLOSE_APPS_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}" or @Name="{ERROR_HEADING_TEXT}"]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, CLOSE_APPS_HEADING_LOCATOR, "CloseAppsHeading", timeout=timeout)

# Added 2026-10-19 (verified against rebit source, not live): CloseApplicationsModel.tsx
# switches the title to CloseApplications_ErrorTitle only when state.hasFailedAttempt --
# that state swaps the footer to Check again (primary) / Retry (secondary). This narrower
# check tells the two states apart; is_showing() above still matches either.
CLOSE_APPS_FAILED_ATTEMPT_HEADING_LOCATOR = ("xpath", f'//*[@Name="{ERROR_HEADING_TEXT}"]')


def is_failed_attempt_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(
        session, CLOSE_APPS_FAILED_ATTEMPT_HEADING_LOCATOR, "CloseAppsFailedAttemptHeading", timeout=timeout
    )
