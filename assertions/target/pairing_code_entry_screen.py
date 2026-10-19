"""Expected heading text + locator + assertion functions for
components.target.pairing_code_entry_screen.PairingCodeEntryScreen ("Let's connect
your two PCs"). Confirmed from a user-supplied flow diagram (dell screens flow.pdf,
2026-10-05), not yet independently confirmed live. Never a click target, so it lives
here rather than in locators/ -- per explicit user direction (2026-10-14).
"""

from assertions.common import gone, text_exists

HEADING_TEXT = "Let's connect your two PCs"
CONNECT_TWO_PCS_HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, CONNECT_TWO_PCS_HEADING_LOCATOR, "ConnectTwoPcsHeading", timeout=timeout)


def wait_until_showing(session, timeout: float) -> bool:
    return text_exists(session, CONNECT_TWO_PCS_HEADING_LOCATOR, "ConnectTwoPcsHeading", timeout=max(timeout, 5.0))


def wait_until_gone(session, timeout: float) -> bool:
    return gone(session, CONNECT_TWO_PCS_HEADING_LOCATOR, "ConnectTwoPcsHeading", timeout=timeout)


# Added 2026-10-19 (verified against rebit source, not live): EnterCodeStage.tsx renders a
# status line under the code boxes keyed on state.status -- EnterCode_StatusVerifying
# ("Verifying ..."), EnterCode_StatusSuccess ("Connection successful"), and
# EnterCode_StatusLocked ("Too many wrong attempts. Try again in {0} minutes." -- the
# minutes are interpolated, hence contains() on the fixed leading phrase). All three use
# contains() on a short apostrophe-free substring rather than an exact match.
LOCKED_STATUS_CONTAINS_TEXT = "Too many wrong attempts"
VERIFYING_STATUS_CONTAINS_TEXT = "Verifying"
CONNECTION_SUCCESSFUL_STATUS_CONTAINS_TEXT = "Connection successful"

LOCKED_STATUS_LOCATOR = ("xpath", f'//*[contains(@Name, "{LOCKED_STATUS_CONTAINS_TEXT}")]')
VERIFYING_STATUS_LOCATOR = ("xpath", f'//*[contains(@Name, "{VERIFYING_STATUS_CONTAINS_TEXT}")]')
CONNECTION_SUCCESSFUL_STATUS_LOCATOR = (
    "xpath",
    f'//*[contains(@Name, "{CONNECTION_SUCCESSFUL_STATUS_CONTAINS_TEXT}")]',
)


def is_locked_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(session, LOCKED_STATUS_LOCATOR, "PairingCodeLockedStatus", timeout=timeout)


def is_verifying_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(session, VERIFYING_STATUS_LOCATOR, "PairingCodeVerifyingStatus", timeout=timeout)


def is_connection_successful_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(
        session, CONNECTION_SUCCESSFUL_STATUS_LOCATOR, "PairingCodeConnectionSuccessfulStatus", timeout=timeout
    )
