"""ReminderFlow: drives the Welcome-back screen's "Remind me later." -> reminder-options
(Tonight/Tomorrow/Next week) -> "Got it" confirmation -> Close round trip, and writes the
local state file utils/notifications/listener.py's deadline-fallback logic reads (see
the notification-automation plan's Design Sec 6, and utils/notifications/state.py for
the shared schema this writes and that module reads).

Confirmed from user-supplied screenshots (2026-10-19). Requires SignInFlow to have been
run with stop_at_welcome_back=True, so the Welcome-back screen is still showing (not
already clicked past) when this flow starts -- see
flows/target/authentication/sign_in_flow.py.

Per CLAUDE.md's "race it continuously" rule: every wait loop here also races the
already-confirmed unpredictable Target dialogs that can appear at any point, not just
during sign-in/transfer -- same dialogs flows/target/transfer_flow.py races.
"""

import time
from datetime import datetime, timedelta, timezone

from assertions.target import (
    desktop_shortcut_dialog as desktop_shortcut_assertions,
    network_disconnected_dialog as network_disconnected_assertions,
    plug_into_ac_power_dialog as plug_into_ac_power_assertions,
    reminder_confirmation_panel as reminder_confirmation_assertions,
    reminder_options_screen as reminder_options_assertions,
    welcome_back_screen as welcome_back_assertions,
)
from components.target.app_window import AppWindow
from components.target.common_dialogs import (
    DesktopShortcutDialog,
    NetworkDisconnectedDialog,
    PlugIntoAcPowerDialog,
)
from components.target.reminder_confirmation_panel import ReminderConfirmationPanel
from components.target.reminder_options_screen import ReminderOptionsScreen
from components.target.sign_in_screen import WelcomeBackScreen
from factory.logger_factory import LoggerFactory
from utils.notifications import state as notification_state

# Real option labels confirmed live (2026-10-19): "Tonight"/"Tomorrow"/"Next week". The
# EXACT trigger-time semantics behind each (a fixed delay from now vs. a fixed clock
# time) are NOT confirmed -- these deltas are a best-effort placeholder, not fact.
REMINDER_DELAYS = {
    "tonight": timedelta(hours=4),
    "tomorrow": timedelta(hours=24),
    "next_week": timedelta(days=7),
}
EXPECTED_FIRE_GRACE = timedelta(minutes=10)


class ReminderFlowError(Exception):
    pass


class ReminderFlow:
    def __init__(self, app_session):
        self.app_session = app_session
        self.welcome_back_screen = WelcomeBackScreen(app_session)
        self.reminder_options_screen = ReminderOptionsScreen(app_session)
        self.reminder_confirmation_panel = ReminderConfirmationPanel(app_session)
        self.app_window = AppWindow(app_session)
        self.network_disconnected_dialog = NetworkDisconnectedDialog(app_session)
        self.plug_into_ac_power_dialog = PlugIntoAcPowerDialog(app_session)
        self.desktop_shortcut_dialog = DesktopShortcutDialog(app_session)
        self.log = LoggerFactory.get_logger("target")

    def _accept_network_disconnected_if_showing(self) -> bool:
        if network_disconnected_assertions.is_showing(self.app_session, timeout=0.1):
            self.network_disconnected_dialog.cancel_transfer()
            self.log.warning("This PC isn't connected to a network. appeared -- clicked Cancel transfer")
            return True
        return False

    def _accept_plug_into_ac_power_if_showing(self) -> bool:
        if plug_into_ac_power_assertions.is_showing(self.app_session, timeout=0.1):
            self.plug_into_ac_power_dialog.click_cancel()
            self.log.warning("Plug into AC power appeared -- waited and clicked Cancel")
            return True
        return False

    def _accept_desktop_shortcut_if_showing(self) -> bool:
        if desktop_shortcut_assertions.is_showing(self.app_session, timeout=0.1):
            self.desktop_shortcut_dialog.click_create_shortcut()
            self.log.warning("Desktop shortcut dialog appeared -- clicked through")
            return True
        return False

    def select_and_confirm(self, option: str, run_id: str, screen_timeout: float = 60.0) -> None:
        """Expects the Welcome-back screen to already be showing (see module docstring
        on SignInFlow(stop_at_welcome_back=True)). Clicks "Remind me later.", waits for
        the reminder-options panel, selects option ("tonight"/"tomorrow"/"next_week"),
        clicks "Set reminder", waits for the "Got it" confirmation, clicks Close, then
        writes the local state file the notification listener's deadline-fallback logic
        depends on.
        """
        if option not in REMINDER_DELAYS:
            raise ValueError(f"Unknown reminder option {option!r} -- expected one of {sorted(REMINDER_DELAYS)}")

        if not welcome_back_assertions.is_showing(self.app_session, timeout=5.0):
            raise ReminderFlowError("Welcome-back screen is not showing -- call this right after SignInFlow(stop_at_welcome_back=True).run()")

        self.welcome_back_screen.click_remind_me_later()

        self.log.info("Waiting for the reminder-options panel...")
        deadline = time.monotonic() + screen_timeout
        while time.monotonic() < deadline:
            if self._accept_network_disconnected_if_showing():
                continue
            if self._accept_plug_into_ac_power_if_showing():
                continue
            if self._accept_desktop_shortcut_if_showing():
                continue
            if reminder_options_assertions.is_showing(self.app_session, timeout=0.5):
                break
        else:
            raise ReminderFlowError("Reminder-options panel never appeared within screen_timeout")

        self.reminder_options_screen.select_option(option)
        self.reminder_options_screen.click_set_reminder()

        self.log.info("Waiting for the Got it confirmation panel...")
        deadline = time.monotonic() + screen_timeout
        while time.monotonic() < deadline:
            if self._accept_network_disconnected_if_showing():
                continue
            if self._accept_plug_into_ac_power_if_showing():
                continue
            if reminder_confirmation_assertions.is_showing(self.app_session, timeout=0.5):
                break
        else:
            raise ReminderFlowError("Got it confirmation panel never appeared within screen_timeout")

        self.log.success(f"Reminder confirmed: option={option!r}")
        self._write_state_file(run_id, option)

        # Bug fixed here, confirmed live (2026-10-19): the "Close" on the "Got it"
        # panel does NOT close the application -- it just dismisses that panel, leaving
        # the Welcome-back screen showing its initial "Ready to get started?" state
        # again (confirmed via a live screenshot after this click). Actually closing the
        # app needs the window's own native title-bar "X" (AutomationId="CloseButton",
        # components/target/app_window.py) -- the same established pattern
        # flows/target/transfer_flow.py already uses after a completed migration, per
        # explicit user direction there (2026-10-14): click the app's own close button
        # rather than leaving the window open for the caller's Session.close() to tear
        # down via a plain process kill. Session.close() still runs regardless
        # (idempotent either way) -- this is a graceful close through the app's own UI
        # first, which also sidesteps the force-kill-looks-like-a-crash relaunch risk
        # documented on factory/session.py::_kill_existing_instances() (nothing needs
        # force-killing if the app already exited gracefully via its own window chrome).
        self.reminder_confirmation_panel.click_close()
        self.app_window.click_close()

    def _write_state_file(self, run_id: str, option: str) -> None:
        expected_fire_by = datetime.now(timezone.utc) + REMINDER_DELAYS[option] + EXPECTED_FIRE_GRACE
        state_path = notification_state.write_pending(run_id, option, expected_fire_by)
        self.log.info(f"Wrote notification state file: {state_path} (expected_fire_by={expected_fire_by.isoformat()})")
