"""Source PC's "We're searching for your new PC." discovery/waiting screen. Confirmed
live (2026-10-06): shown after "Let's get started" (and the trust-network dialog, when
present), and stays showing until a real Target PC becomes discoverable on the network --
it does not advance on its own after a fixed timeout.
"""

from components.base_component import BaseComponent
from locators.source.searching_screen import HEADING_LOCATOR


class SearchingScreen:
    def __init__(self, app_session):
        self._heading = BaseComponent(app_session, *HEADING_LOCATOR, "SearchingForNewPcHeading")

    def is_showing(self, timeout: float = 2.0) -> bool:
        return self._heading.exists(timeout=timeout)
