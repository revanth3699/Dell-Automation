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
