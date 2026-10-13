"""Source-role post-pairing transfer sequence: "We've successfully linked your PCs."
-> "Are you ready to start your migration?" -> "We're migrating your data now." ->
one of THREE final screens -- "We've completed your migration." (full success) and
"Your migration summary is ready." (one of two partial-migration outcomes) both have a
"Close" button; "Your migration is now complete." (the OTHER partial-migration
outcome) has a "Try Again" button but no "Close" button -- only its own top-right close
icon -- or the recoverable "We ran into a problem during your migration." error screen
(its own "Try Again" button, restarts the migration). See
locators/source/transfer_progress_screen.py for why these need separate click targets.

Per explicit user direction (2026-10-14): every existence check
(is_linked_success()/is_ready_to_migrate()/is_migrating()/
is_migration_complete_confirmed()/is_migration_partial_try_again_confirmed()/
is_migration_partial_summary_confirmed()/is_migration_error_confirmed()) lives in
assertions/source/transfer_progress_screen.py, called directly from flows/ -- this
class holds only the click_close()/click_close_after_delay()/click_close_icon()/
click_try_again() actions.

Bug fixed here, per explicit user direction (2026-10-13): "Your migration summary is
ready." (one of the two partial-migration outcomes) used to be dismissed via
click_close() immediately, same as the full-success screen. Now waits
PARTIAL_SUMMARY_CLOSE_DELAY_SECONDS first via click_close_after_delay() -- giving the
user a real chance to read the summary and use "Show skipped files"/Retry before it's
dismissed -- same "wait before dismissing" pattern as BatteryCriticallyLowDialog /
Target's PlugIntoAcPowerDialog. The full-success screen's click_close() is untouched --
this delay is specific to the partial-summary screen (see
flows/source/transfer_flow.py's wait_for_migration_to_complete()).
"""

import time

from components.base_component import BaseComponent
from locators.source.transfer_progress_screen import (
    CLOSE_BUTTON_LOCATOR,
    CLOSE_ICON_LOCATOR,
    TRY_AGAIN_BUTTON_LOCATOR,
)


class TransferProgressScreen:
    PARTIAL_SUMMARY_CLOSE_DELAY_SECONDS = 20.0

    def __init__(self, app_session):
        self._close_button = BaseComponent(app_session, *CLOSE_BUTTON_LOCATOR, "TransferProgressCloseButton")
        self._close_icon = BaseComponent(app_session, *CLOSE_ICON_LOCATOR, "TransferProgressCloseIcon")
        self._try_again_button = BaseComponent(app_session, *TRY_AGAIN_BUTTON_LOCATOR, "TransferProgressTryAgainButton")

    def click_close(self) -> None:
        """Full-success screen's "Close" button -- clicked immediately."""
        self._close_button.click()

    def click_close_after_delay(self) -> None:
        """"Your migration summary is ready." (partial) screen's "Close" button --
        same button as click_close(), but waits PARTIAL_SUMMARY_CLOSE_DELAY_SECONDS
        first (see module docstring)."""
        time.sleep(self.PARTIAL_SUMMARY_CLOSE_DELAY_SECONDS)
        self._close_button.click()

    def click_close_icon(self) -> None:
        """Partial-migration screen's top-right close icon -- it has no "Close"
        button, so click_close() above does not apply here."""
        self._close_icon.click()

    def click_try_again(self) -> None:
        """Recoverable error screen's "Try Again" button -- restarts the migration."""
        self._try_again_button.click()
