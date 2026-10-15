"""
Target PC app-side dialog/modal elements that can appear on top of other screens during
the sign-in sequence (Target-only: Source PC has no authentication step). See
PROJECT_PLAN.md Sec 5.3/5.4 and tools/phase0_inspection_notes.md for how each was
confirmed.

Per explicit user direction (2026-10-14): existence checks ("assertions") no longer
live here -- each dialog's is_showing() moved to its own assertions/target/<name>.py
(built on assertions/common.py's text_exists()/button_exists() methods) and is called
directly from flows/. These classes now hold ONLY click actions; every former
accept()/retry()/cancel() (check-then-click in one call) is now a pure click_X()
action -- callers check is_showing() first, then click. MigrationPreparationTransition
(a raw page-source poll, not an XPath lookup at all) moved out entirely to
assertions/target/migration_preparation_transition.py as a plain function, since it had
no action to keep here.
"""

import time

from components.base_component import BaseComponent
from locators.target.close_apps_dialog import CLOSE_APPLICATION_BUTTON_LOCATOR
from locators.target.desktop_shortcut_dialog import CREATE_SHORTCUT_BUTTON_LOCATOR
from locators.target.install_browsers_to_migrate_bookmarks_dialog import (
    RESCAN_BUTTON_LOCATOR,
    SKIP_BUTTON_LOCATOR,
)
from locators.target.migration_error_dialog import MIGRATION_ERROR_BODY_LOCATOR
from locators.target.network_disconnected_dialog import NETWORK_DISCONNECTED_CANCEL_TRANSFER_BUTTON_LOCATOR
from locators.target.other_pc_network_disconnected_dialog import CANCEL_TRANSFER_BUTTON_LOCATOR
from locators.target.plug_into_ac_power_dialog import PLUG_INTO_AC_POWER_CANCEL_BUTTON_LOCATOR
from locators.target.regional_settings_not_supported_dialog import CLOSE_BUTTON_LOCATOR as REGIONAL_SETTINGS_CLOSE_BUTTON_LOCATOR
from locators.target.sign_in_failed_dialog import SIGN_IN_FAILED_RETRY_BUTTON_LOCATOR
from locators.target.sign_in_waiting_modal import SIGN_IN_WAITING_CANCEL_BUTTON_LOCATOR
from locators.target.trust_network_dialog import TRUST_NETWORK_BUTTON_LOCATOR


class TrustNetworkDialog:
    """"Connect to a trusted network" dialog, confirmed appearing after sign-in. See
    assertions/target/trust_network_dialog.py's is_showing() for the presence check --
    callers check that first, then click_trust_network() here."""

    def __init__(self, app_session):
        self._button = BaseComponent(app_session, *TRUST_NETWORK_BUTTON_LOCATOR, "TrustNetworkButton")

    def click_trust_network(self) -> None:
        # Confirmed live (2026-10-07): click() previously re-found the button with its
        # full default timeout (10s) even though the caller's is_showing() just
        # confirmed it's there -- if that fresh lookup is at all flaky, the click alone
        # could take many seconds. Short timeout here since presence was just confirmed.
        self._button.click(timeout=2.0)


class SignInFailedDialog:
    """"We couldn't sign you in" (confirmed via a live screenshot, 2026-10-14 -- an
    earlier assumed heading, "There was a problem signing in", was never actually seen
    live and never matched) -- shown layered over the Welcome screen when
    authentication fails or is cancelled. Has a Cancel and a Retry button. See
    assertions/target/sign_in_failed_dialog.py's is_showing().

    Critically, the user confirmed directly that the migration-preparation transition
    screen can appear even when sign-in was actually cancelled -- so that screen's
    appearance ALONE is not a reliable success signal. This dialog is the other half of
    the race: whichever of the two appears first after OTP submission is what actually
    tells success and failure apart (see SignInFlow._wait_for_auth_outcome).
    """

    def __init__(self, app_session):
        self._retry_button = BaseComponent(
            app_session, *SIGN_IN_FAILED_RETRY_BUTTON_LOCATOR, "SignInFailedRetryButton"
        )

    def click_retry(self) -> None:
        self._retry_button.click()


class SignInWaitingModal:
    """"Sign in to MyDell to continue" -- shown in the app (not the browser) while the
    external browser-based sign-in is in progress. Confirmed to exist from the project's
    original reference walkthrough; this is the deliberate, user-confirmed way to force a
    real sign-in cancellation for testing the cancel-and-retry path (see
    tools/_test_cancel_and_retry_live.py) -- NOT something a flow clicks as part of normal
    operation (see tools/signin_flow_test_plan.md's exclusion list). See
    assertions/target/sign_in_waiting_modal.py's is_showing().

    The Cancel button's exact accessible name is unconfirmed live -- see
    locators/target/sign_in_waiting_modal.py.
    """

    def __init__(self, app_session):
        self._cancel_button = BaseComponent(
            app_session, *SIGN_IN_WAITING_CANCEL_BUTTON_LOCATOR, "SignInWaitingCancelButton"
        )

    def click_cancel(self) -> None:
        self._cancel_button.click()


class CloseAppsDialog:
    """"We need to close all other applications" -- shown when the app detects other
    running applications (e.g. Control Panel, a browser) blocking migration. Confirmed
    from a user-supplied screenshot (2026-10-06). Can appear unpredictably during a long
    wait (same as ConfirmAccountsDialog), not tied to one specific prior step. See
    assertions/target/close_apps_dialog.py's is_showing().
    """

    def __init__(self, app_session):
        self._close_application_button = BaseComponent(
            app_session, *CLOSE_APPLICATION_BUTTON_LOCATOR, "CloseApplicationButton"
        )

    def click_close_application(self) -> None:
        self._close_application_button.click()


class NetworkDisconnectedDialog:
    """"This PC isn't connected to a network." -- a generic connectivity-check dialog
    that can appear at any point during a pairing-dependent wait, not tied to one
    specific screen (confirmed directly by the user, 2026-10-15: can appear in ANY
    phase -- sign-in, pairing, or mid-transfer).

    Bug fixed here, confirmed live via a user-supplied screenshot (2026-10-15): this
    class was originally built from two 2026-10-09 screenshots assumed to show a
    "Check again" button -- live evidence now shows the dialog has exactly one button,
    "Cancel transfer", and no retry option at all. That earlier locator never matched
    anything, so every click attempt here silently no-op'd (waited, found no button,
    returned) while callers logged a false "clicked Check again" message regardless.

    Confirmed directly by the user (2026-10-15): clicking "Cancel transfer" does NOT
    abort the run -- same reset behavior as PlugIntoAcPowerDialog -- it bounces all the
    way back to the "Welcome back" home screen, which needs its own blue "Get started"
    button clicked again to re-enter. If the network is still down, the dialog just
    reappears after re-entry -- per explicit user direction, this cycle (Cancel
    transfer -> Get started -> re-check) is expected to repeat until the network
    actually comes back; re-establishing it is the user's own responsibility, not
    something this automation resolves on its own. Each flow that races this dialog
    (SignInFlow, TargetPairingFlow, TargetTransferFlow) owns its own
    click-Get-started-and-continue handling, same split as PlugIntoAcPowerDialog. See
    assertions/target/network_disconnected_dialog.py's is_showing().
    """

    def __init__(self, app_session):
        self._cancel_transfer_button = BaseComponent(
            app_session, *NETWORK_DISCONNECTED_CANCEL_TRANSFER_BUTTON_LOCATOR, "NetworkDisconnectedCancelTransferButton"
        )

    def cancel_transfer(self, timeout: float = 2.0) -> None:
        """Clicks "Cancel transfer". Callers check is_showing() first and only call
        this once they already know the dialog is present -- this never re-checks
        presence itself."""
        self._cancel_transfer_button.click(timeout=timeout)


class PlugIntoAcPowerDialog:
    """"Plug into AC power" -- a low-battery warning confirmed from a user-supplied
    screenshot (2026-10-12). Can appear layered over any screen during the migration --
    not tied to one specific step, same "race it continuously" treatment as
    NetworkDisconnectedDialog. See assertions/target/plug_into_ac_power_dialog.py's
    is_showing().

    Per explicit user direction: waits PLUG_IN_DELAY_SECONDS before clicking Cancel
    (rather than immediately), giving the user a real chance to actually plug the PC in
    before dismissing the warning.

    Bug fixed here, confirmed live (2026-10-14): a real run's log showed the heading
    detected (PlugIntoAcPowerHeading: True), then click_cancel()'s click failing
    outright ("Condition not met within 2.0s") after the 15s wait, repeatedly, every
    single cycle across two separate real runs -- an initial guess (the dialog
    clearing itself during the wait) turned out wrong, confirmed by attaching
    read-only to a real session with the dialog actually showing: the button's real
    accessible name is "Cancel transfer", not "Cancel" -- see
    locators/target/plug_into_ac_power_dialog.py. The real bug was a wrong locator,
    not a race; it just happened to fail the same way every time instead of
    intermittently. click_cancel() still re-checks the button's own existence right
    after the delay and no-ops if it's gone (kept as defensive insurance against the
    genuine race this was originally mistaken for -- e.g. power really does get
    plugged in during the wait), but the real fix is the corrected locator.
    """

    PLUG_IN_DELAY_SECONDS = 15.0

    def __init__(self, app_session):
        self._cancel_button = BaseComponent(
            app_session, *PLUG_INTO_AC_POWER_CANCEL_BUTTON_LOCATOR, "PlugIntoAcPowerCancelButton"
        )

    def click_cancel(self) -> None:
        time.sleep(self.PLUG_IN_DELAY_SECONDS)
        if not self._cancel_button.exists(timeout=1.0):
            return
        self._cancel_button.click(timeout=2.0)


class OtherPcNetworkDisconnectedDialog:
    """"The other PC isn't connected to a network." -- confirmed from a user-supplied
    screenshot (2026-10-12), shown layered over the transfer-progress screen. Distinct
    from NetworkDisconnectedDialog ("This PC isn't connected to a network."), which is
    about THIS machine's own connectivity and is recoverable by waiting and clicking
    "Check again". This one reports the REMOTE (Source) PC losing its network
    connection -- nothing local to retry, the problem is on the other machine -- so per
    explicit user direction this is treated as a terminal failure, not something to
    race and recover from: click "Cancel transfer" and let the caller abort the whole
    run. See assertions/target/other_pc_network_disconnected_dialog.py's is_showing().
    """

    def __init__(self, app_session):
        self._cancel_transfer_button = BaseComponent(
            app_session, *CANCEL_TRANSFER_BUTTON_LOCATOR, "CancelTransferButton"
        )

    def cancel_transfer(self, timeout: float = 2.0) -> None:
        """Clicks "Cancel transfer". Callers check is_showing() first and only call
        this once they already know the dialog is present -- this never re-checks
        presence itself."""
        self._cancel_transfer_button.click(timeout=timeout)


class DesktopShortcutDialog:
    """"Add a desktop shortcut before you go" -- confirmed from a user-supplied
    screenshot (2026-10-13): shown at any point between app launch and reaching
    pairing-discovery, offering to create a desktop shortcut back into the app via
    SupportAssist. Has "No, thanks" and "Create shortcut" buttons -- per explicit user
    direction, always clicks "Create shortcut". See
    assertions/target/desktop_shortcut_dialog.py's is_showing().
    """

    def __init__(self, app_session):
        self._create_shortcut_button = BaseComponent(
            app_session, *CREATE_SHORTCUT_BUTTON_LOCATOR, "CreateShortcutButton"
        )

    def click_create_shortcut(self) -> None:
        self._create_shortcut_button.click()


class RegionalSettingsNotSupportedDialog:
    """"Set both of your PCs to the same supported region" -- confirmed from a live run
    (2026-10-14), appearing while Target waits for pairing-discovery right after
    sign-in: Target and Source PCs are set to different, incompatible regions.
    Confirmed directly by the user: Target-only, and treated as an immediate,
    unrecoverable failure -- click Close, then the caller raises and aborts the run,
    same terminal pattern as OtherPcNetworkDisconnectedDialog. See
    assertions/target/regional_settings_not_supported_dialog.py's is_showing() (and its
    own docstring for the heading-text correction history).
    """

    def __init__(self, app_session):
        self._close_button = BaseComponent(
            app_session, *REGIONAL_SETTINGS_CLOSE_BUTTON_LOCATOR, "RegionalSettingsNotSupportedCloseButton"
        )

    def click_close(self, timeout: float = 2.0) -> None:
        """Clicks Close. Callers check is_showing() first and only call this once they
        already know the dialog is present -- this never re-checks presence itself."""
        self._close_button.click(timeout=timeout)


class InstallBrowsersToMigrateBookmarksDialog:
    """"Install one or more browsers to migrate your bookmarks" -- confirmed from a
    user-supplied screenshot (2026-10-14): appears right after clicking the migrate
    button ("Bring everything over for me") when the Source PC has a browser (e.g.
    Firefox) installed that this (Target) PC doesn't, so that browser's bookmarks
    can't be migrated. Has "Skip" and "Rescan" buttons. Not fatal -- per explicit user
    direction, click_rescan() waits RESCAN_DELAY_SECONDS then clicks Rescan (giving it
    one chance in case the browser gets installed/detected in the meantime);
    click_skip() is a separate, plain click so the caller can re-check is_showing()
    between the two (see flows/target/transfer_flow.py) and skip the second click if
    Rescan already cleared the dialog. See
    assertions/target/install_browsers_to_migrate_bookmarks_dialog.py's is_showing().
    """

    RESCAN_DELAY_SECONDS = 10.0

    def __init__(self, app_session):
        self._rescan_button = BaseComponent(app_session, *RESCAN_BUTTON_LOCATOR, "InstallBrowsersRescanButton")
        self._skip_button = BaseComponent(app_session, *SKIP_BUTTON_LOCATOR, "InstallBrowsersSkipButton")

    def click_rescan(self) -> None:
        time.sleep(self.RESCAN_DELAY_SECONDS)
        self._rescan_button.click(timeout=2.0)

    def click_skip(self) -> None:
        self._skip_button.click(timeout=2.0)


class MigrationErrorDialog:
    """"Something went wrong" -- a fatal engine-side error during migration prep/transfer
    (e.g. "error 2969"). Confirmed from a user-supplied screenshot (2026-10-08) appearing
    layered over the transfer-progress screen. See
    assertions/target/migration_error_dialog.py's is_showing().

    Treated as an immediate, unrecoverable migration failure -- no click action here,
    unlike every other dialog in this module. Those are all meant to be clicked through
    so the flow can continue; this one means the whole run should stop and raise, so
    callers check is_showing() and raise their own error immediately (see
    flows/target/transfer_flow.py), using read_error_text() to surface the real error
    code instead of a generic timeout message.
    """

    def __init__(self, app_session):
        self._body = BaseComponent(app_session, *MIGRATION_ERROR_BODY_LOCATOR, "MigrationErrorBody")

    def read_error_text(self, timeout: float = 2.0) -> str:
        """Best-effort: returns the body text for a clearer failure message. Never
        raises -- evidence-gathering must never mask the real failure that's about to
        be raised by the caller."""
        try:
            return self._body.get_text(timeout=timeout)
        except Exception:
            return "(error text unavailable)"
