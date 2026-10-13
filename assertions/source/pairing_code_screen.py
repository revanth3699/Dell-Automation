"""Expected heading text + locator + assertion function for
components.source.pairing_code_screen.PairingCodeScreen ("Let's finish linking your
PCs."). Confirmed live (2026-10-06) via Phase 0 spike against the real Source build.
Never a click target, so it lives here rather than in locators/ -- per explicit user
direction (2026-10-14).
"""

from assertions.common import text_exists

HEADING_TEXT = "Let's finish linking your PCs."
HEADING_LOCATOR = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, HEADING_LOCATOR, "PairingCodeHeading", timeout=timeout)
