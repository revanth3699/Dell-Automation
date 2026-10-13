"""Expected heading text + locator + assertion functions for the Target
pairing-discovery screen ("We're looking for your other PC"). No corresponding
component exists -- this screen has no action of its own, only these checks, called
directly from flows/. The heading locator lives here, not in locators/, since it is
never a click target -- per explicit user direction (2026-10-14: locators used purely
for assertion live in assertions/, alongside the text and the poll+assert function
built from the common assertions/common.py methods).
"""

from assertions.common import gone, text_exists

HEADING_TEXT = "We're looking for your other PC"
LOOKING_FOR_OTHER_PC_HEADING = ("xpath", f'//*[@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, LOOKING_FOR_OTHER_PC_HEADING, "LookingForOtherPcHeading", timeout=timeout)


def wait_until_showing(session, timeout: float) -> bool:
    return text_exists(session, LOOKING_FOR_OTHER_PC_HEADING, "LookingForOtherPcHeading", timeout=max(timeout, 5.0))


def wait_until_source_found(session, timeout: float) -> bool:
    """True once this screen clears (Source PC was found) within timeout; False if
    it's still showing once it expires."""
    return gone(session, LOOKING_FOR_OTHER_PC_HEADING, "LookingForOtherPcHeading", timeout=timeout)
