"""Source-role post-pairing transfer sequence: "We've successfully linked your PCs."
-> "Are you ready to start your migration?" -> "We're migrating your data now." ->
one of two final screens, "We've completed your migration." (full success) or "Your
migration summary is ready." (partial migration) -- both have a "Close" button with the
same accessible name, so one click action covers either.

Per explicit user direction (2026-10-14): every existence check
(is_linked_success()/is_ready_to_migrate()/is_migrating()/
is_migration_complete_confirmed()/is_summary_confirmed()) moved out to
assertions/source/transfer_progress_screen.py, called directly from flows/ -- this
class now holds only the click_close() action.
"""

from components.base_component import BaseComponent
from locators.source.transfer_progress_screen import CLOSE_BUTTON_LOCATOR


class TransferProgressScreen:
    def __init__(self, app_session):
        self._close_button = BaseComponent(app_session, *CLOSE_BUTTON_LOCATOR, "TransferProgressCloseButton")

    def click_close(self) -> None:
        self._close_button.click()
