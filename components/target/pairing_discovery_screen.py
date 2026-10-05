"""
Target-side "We're looking for your other PC" screen -- shown while Target searches
for Source over the LAN. Confirmed directly by the user (2026-10-05): this screen can
appear at any point (whether sign-in was fresh or already-logged-in) and simply means
Source isn't ready/discoverable yet; the screen changes on its own once it is.

SignInFlow.run()'s confirmed end state is reaching this screen, not waiting past it --
wait_until_source_found() below is exposed separately (called explicitly by a caller
after run() succeeds, not from inside run() itself) so that boundary stays intact. What
specifically appears once Source is found is pairing-flow work -- see
components/target/pairing_code_entry_screen.py and flows/target/pairing_flow.py.
"""

from components.base_component import BaseComponent
from locators.target.pairing_discovery_screen import LOOKING_FOR_OTHER_PC_HEADING


class PairingDiscoveryScreen:
    def __init__(self, app_session):
        self._heading = BaseComponent(app_session, *LOOKING_FOR_OTHER_PC_HEADING, "LookingForOtherPcHeading")

    def is_showing(self, timeout: float = 2.0) -> bool:
        return self._heading.exists(timeout=timeout)

    def wait_until_showing(self, timeout: float) -> bool:
        return self._heading.exists(timeout=max(timeout, 5.0))

    def wait_until_source_found(self, timeout: float) -> bool:
        """True once this screen clears (Source PC was found) within timeout; False if
        it's still showing once it expires. Confirmed by the user (2026-10-05): this
        applies the same way whether this screen was reached via a fresh sign-in or via
        an already-logged-in shortcut -- in both cases it just means Source isn't
        discoverable yet, and the screen changes on its own once it is. Uses
        wait_until_gone(), not a repeated is_showing() poll -- see
        BaseComponent.wait_until_gone()'s docstring for why that distinction matters.
        """
        return self._heading.wait_until_gone(timeout=timeout)
