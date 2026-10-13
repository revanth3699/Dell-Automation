"""Expected heading text + locator + assertion function for the Source "We're
searching for your new PC." discovery screen. Confirmed live (2026-10-06): shown after
"Let's get started" (and, when present, after accepting the trust-network dialog), and
stays showing until a real Target PC becomes discoverable on the network. Never a click
target, so it lives here rather than in locators/ -- per explicit user direction
(2026-10-14). No corresponding component exists -- this screen has no action of its
own, only this check, called directly from flows/.
"""

from assertions.common import text_exists

HEADING_TEXT = "We're searching for your new PC."
HEADING_LOCATOR = ("xpath", f'//*[@AutomationId="TxtProgressPageTitle"][@Name="{HEADING_TEXT}"]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, HEADING_LOCATOR, "SearchingForNewPcHeading", timeout=timeout)
