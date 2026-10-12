"""
Target PC app-side dialog/modal elements that can appear on top of other screens during
the sign-in sequence (Target-only: Source PC has no authentication step). See
PROJECT_PLAN.md Sec 5.3/5.4 and tools/phase0_inspection_notes.md for how each was
confirmed.
"""

import time
from typing import Optional

from components.base_component import BaseComponent
from locators.target.close_apps_dialog import CLOSE_APPLICATION_BUTTON_LOCATOR, CLOSE_APPS_HEADING_LOCATOR
from locators.target.desktop_shortcut_dialog import (
    CREATE_SHORTCUT_BUTTON_LOCATOR,
    DESKTOP_SHORTCUT_HEADING_LOCATOR,
)
from assertions.target.migration_preparation_transition import TRANSITION_PHRASES
from locators.target.migration_error_dialog import MIGRATION_ERROR_BODY_LOCATOR, MIGRATION_ERROR_HEADING_LOCATOR
from locators.target.network_disconnected_dialog import CHECK_AGAIN_BUTTON_LOCATOR, NETWORK_DISCONNECTED_HEADING_LOCATOR
from locators.target.other_pc_network_disconnected_dialog import (
    CANCEL_TRANSFER_BUTTON_LOCATOR,
    OTHER_PC_NETWORK_DISCONNECTED_HEADING_LOCATOR,
)
from locators.target.plug_into_ac_power_dialog import (
    PLUG_INTO_AC_POWER_CANCEL_BUTTON_LOCATOR,
    PLUG_INTO_AC_POWER_HEADING_LOCATOR,
)
from locators.target.sign_in_failed_dialog import SIGN_IN_FAILED_HEADING_LOCATOR, SIGN_IN_FAILED_RETRY_BUTTON_LOCATOR
from locators.target.sign_in_waiting_modal import SIGN_IN_WAITING_HEADING_LOCATOR, SIGN_IN_WAITING_CANCEL_BUTTON_LOCATOR
from locators.target.trust_network_dialog import TRUST_NETWORK_BUTTON_LOCATOR, TRUST_NETWORK_HEADING_LOCATOR


class TrustNetworkDialog:
    """"Connect to a trusted network" dialog, confirmed appearing after sign-in.

    Simplified here, per explicit user direction (2026-10-07): checks the dialog's own
    heading ("Connect to a trusted network") rather than the button directly -- the
    button can be visible but disabled while the dialog shows "Trusting this
    network..." mid-transition (confirmed via a live screenshot showing both Cancel and
    Trust Network greyed out during that moment), so finding it existing wasn't the
    same as it actually being clickable. Same heading-then-button pattern already used
    by ConfirmAccountsDialog/SignInFailedDialog.
    """

    def __init__(self, app_session):
        self._heading = BaseComponent(app_session, *TRUST_NETWORK_HEADING_LOCATOR, "TrustNetworkHeading")
        self._button = BaseComponent(app_session, *TRUST_NETWORK_BUTTON_LOCATOR, "TrustNetworkButton")

    def is_showing(self, timeout: float = 2.0) -> bool:
        return self._heading.exists(timeout=timeout)

    def accept(self, timeout: float = 2.0) -> bool:
        """Clicks "Trust Network" if the dialog is showing. Returns whether it was
        present at all, so callers can distinguish "already past this dialog" from
        "accepted it just now" without a separate is_showing() call.

        Confirmed live (2026-10-07): click() previously re-found the button with its
        full default timeout (10s) even though exists() just confirmed it's there --
        if that fresh lookup is at all flaky, the click alone could take many seconds.
        Passes a short timeout here since presence was just confirmed above.
        """
        if not self._heading.exists(timeout=timeout):
            return False
        self._button.click(timeout=2.0)
        return True


class SignInFailedDialog:
    """"There was a problem signing in" / "Sign-in failed. Please try again." -- shown
    layered over the Welcome screen when authentication fails or is cancelled. Confirmed
    from a user-supplied flow diagram ("dell screens flow.pdf", 2026-10-05): has a Cancel
    and a Retry button.

    Critically, the user confirmed directly that MigrationPreparationTransition's own
    transition screen (below) can appear even when sign-in was actually cancelled -- so
    that screen's appearance ALONE is not a reliable success signal. This dialog is the
    other half of the race: whichever of the two appears first after OTP submission is
    what actually tells success and failure apart (see SignInFlow._wait_for_auth_outcome).
    """

    def __init__(self, app_session):
        self._heading = BaseComponent(app_session, *SIGN_IN_FAILED_HEADING_LOCATOR, "SignInFailedHeading")
        self._retry_button = BaseComponent(
            app_session, *SIGN_IN_FAILED_RETRY_BUTTON_LOCATOR, "SignInFailedRetryButton"
        )

    def is_showing(self, timeout: float = 0.1) -> bool:
        return self._heading.exists(timeout=timeout)

    def retry(self, timeout: float = 2.0) -> bool:
        """Clicks Retry if the dialog is showing. Returns whether it was present at all
        (same pattern as TrustNetworkDialog.accept()).
        """
        if not self._heading.exists(timeout=timeout):
            return False
        self._retry_button.click()
        return True


class SignInWaitingModal:
    """"Sign in to MyDell to continue" -- shown in the app (not the browser) while the
    external browser-based sign-in is in progress: "We've opened your web browser so you
    can sign in and continue...", a "Having trouble? Retry" link, a "Waiting for
    sign-in..." status, and a Cancel button. Confirmed to exist from the project's
    original reference walkthrough; this is the deliberate, user-confirmed way to force a
    real sign-in cancellation for testing the cancel-and-retry path (see
    tools/_test_cancel_and_retry_live.py) -- NOT something a flow clicks as part of normal
    operation (see tools/signin_flow_test_plan.md's exclusion list).

    The Cancel button's exact accessible name is unconfirmed live -- see
    locators/target/sign_in_waiting_modal.py.
    """

    def __init__(self, app_session):
        self._heading = BaseComponent(app_session, *SIGN_IN_WAITING_HEADING_LOCATOR, "SignInWaitingHeading")
        self._cancel_button = BaseComponent(
            app_session, *SIGN_IN_WAITING_CANCEL_BUTTON_LOCATOR, "SignInWaitingCancelButton"
        )

    def is_showing(self, timeout: float = 2.0) -> bool:
        return self._heading.exists(timeout=timeout)

    def cancel(self, timeout: float = 2.0) -> bool:
        """Clicks Cancel if the modal is showing. Returns whether it was present at all
        (same pattern as TrustNetworkDialog.accept()).
        """
        if not self._heading.exists(timeout=timeout):
            return False
        self._cancel_button.click()
        return True


class CloseAppsDialog:
    """"We need to close all other applications" -- shown when the app detects other
    running applications (e.g. Control Panel, a browser) blocking migration. Confirmed
    from a user-supplied screenshot (2026-10-06). Can appear unpredictably during a long
    wait (same as ConfirmAccountsDialog), not tied to one specific prior step.
    """

    def __init__(self, app_session):
        self._heading = BaseComponent(app_session, *CLOSE_APPS_HEADING_LOCATOR, "CloseAppsHeading")
        self._close_application_button = BaseComponent(
            app_session, *CLOSE_APPLICATION_BUTTON_LOCATOR, "CloseApplicationButton"
        )

    def is_showing(self, timeout: float = 2.0) -> bool:
        return self._heading.exists(timeout=timeout)

    def accept(self, timeout: float = 2.0) -> bool:
        """Clicks "Close Application" if the dialog is showing. Returns whether it was
        present at all (same pattern as TrustNetworkDialog.accept()).
        """
        if not self._heading.exists(timeout=timeout):
            return False
        self._close_application_button.click()
        return True


class NetworkDisconnectedDialog:
    """"This PC isn't connected to a network." -- a generic connectivity-check dialog
    confirmed from two user-supplied screenshots (2026-10-09), each showing it layered
    over a different underlying screen -- can appear at any point during a
    pairing-dependent wait (the body text, "Connect both of your PCs to the same
    network to continue", ties it to the cross-machine discovery/pairing step
    specifically), not tied to one specific screen. Has a "Check again" button.

    Per explicit user direction: waits CHECK_AGAIN_DELAY_SECONDS before clicking Check
    again (rather than immediately), since the underlying network condition is likely
    transient -- an instant re-check would probably just hit the same failure again.
    """

    CHECK_AGAIN_DELAY_SECONDS = 30.0

    def __init__(self, app_session):
        self._heading = BaseComponent(
            app_session, *NETWORK_DISCONNECTED_HEADING_LOCATOR, "NetworkDisconnectedHeading"
        )
        self._check_again_button = BaseComponent(app_session, *CHECK_AGAIN_BUTTON_LOCATOR, "CheckAgainButton")

    def is_showing(self, timeout: float = 0.1) -> bool:
        return self._heading.exists(timeout=timeout)

    def accept(self, timeout: float = 2.0) -> bool:
        """Clicks "Check again" if the dialog is showing, after waiting
        CHECK_AGAIN_DELAY_SECONDS first. Returns whether it was present at all (same
        pattern as every other dialog in this module)."""
        if not self._heading.exists(timeout=timeout):
            return False
        time.sleep(self.CHECK_AGAIN_DELAY_SECONDS)
        self._check_again_button.click(timeout=2.0)
        return True


class PlugIntoAcPowerDialog:
    """"Plug into AC power" -- a low-battery warning confirmed from a user-supplied
    screenshot (2026-10-12): "Be sure this PC is plugged into AC power to avoid delays
    while we migrate your files and settings." Can appear layered over any screen
    during the migration -- not tied to one specific step, same "race it continuously"
    treatment as NetworkDisconnectedDialog.

    Per explicit user direction: waits PLUG_IN_DELAY_SECONDS before clicking Cancel
    (rather than immediately), giving the user a real chance to actually plug the PC in
    before dismissing the warning.
    """

    PLUG_IN_DELAY_SECONDS = 15.0

    def __init__(self, app_session):
        self._heading = BaseComponent(
            app_session, *PLUG_INTO_AC_POWER_HEADING_LOCATOR, "PlugIntoAcPowerHeading"
        )
        self._cancel_button = BaseComponent(
            app_session, *PLUG_INTO_AC_POWER_CANCEL_BUTTON_LOCATOR, "PlugIntoAcPowerCancelButton"
        )

    def is_showing(self, timeout: float = 0.1) -> bool:
        return self._heading.exists(timeout=timeout)

    def accept(self, timeout: float = 2.0) -> bool:
        """Clicks Cancel if the dialog is showing, after waiting PLUG_IN_DELAY_SECONDS
        first. Returns whether it was present at all (same pattern as every other
        dialog in this module)."""
        if not self._heading.exists(timeout=timeout):
            return False
        time.sleep(self.PLUG_IN_DELAY_SECONDS)
        self._cancel_button.click(timeout=2.0)
        return True


class OtherPcNetworkDisconnectedDialog:
    """"The other PC isn't connected to a network." -- confirmed from a user-supplied
    screenshot (2026-10-12), shown layered over the transfer-progress screen. Distinct
    from NetworkDisconnectedDialog ("This PC isn't connected to a network."), which is
    about THIS machine's own connectivity and is recoverable by waiting and clicking
    "Check again". This one reports the REMOTE (Source) PC losing its network
    connection -- nothing local to retry, the problem is on the other machine -- so per
    explicit user direction this is treated as a terminal failure, not something to
    race and recover from: click "Cancel transfer" and let the caller abort the whole
    run (same "immediate, unrecoverable" treatment as MigrationErrorDialog, just with
    its own explicit button to click first instead of nothing to click at all).
    """

    def __init__(self, app_session):
        self._heading = BaseComponent(
            app_session, *OTHER_PC_NETWORK_DISCONNECTED_HEADING_LOCATOR, "OtherPcNetworkDisconnectedHeading"
        )
        self._cancel_transfer_button = BaseComponent(
            app_session, *CANCEL_TRANSFER_BUTTON_LOCATOR, "CancelTransferButton"
        )

    def is_showing(self, timeout: float = 0.1) -> bool:
        return self._heading.exists(timeout=timeout)

    def cancel_transfer(self, timeout: float = 2.0) -> None:
        """Clicks "Cancel transfer". Callers check is_showing() first and only call
        this once they already know the dialog is present (same convention as
        MigrationErrorDialog.read_error_text()) -- unlike every other dialog's
        accept()/retry(), this doesn't re-check presence itself."""
        self._cancel_transfer_button.click(timeout=timeout)


class DesktopShortcutDialog:
    """"Add a desktop shortcut before you go" -- confirmed from a user-supplied
    screenshot (2026-10-13): shown near the very end of the Target flow (per its own
    "before you go" wording), offering to create a desktop shortcut back into the app
    via SupportAssist. Has "No, thanks" and "Create shortcut" buttons -- per explicit
    user direction, accept() always clicks "Create shortcut".
    """

    def __init__(self, app_session):
        self._heading = BaseComponent(app_session, *DESKTOP_SHORTCUT_HEADING_LOCATOR, "DesktopShortcutHeading")
        self._create_shortcut_button = BaseComponent(
            app_session, *CREATE_SHORTCUT_BUTTON_LOCATOR, "CreateShortcutButton"
        )

    def is_showing(self, timeout: float = 0.1) -> bool:
        return self._heading.exists(timeout=timeout)

    def accept(self, timeout: float = 2.0) -> bool:
        """Clicks "Create shortcut" if the dialog is showing. Returns whether it was
        present at all (same pattern as every other dialog in this module)."""
        if not self._heading.exists(timeout=timeout):
            return False
        self._create_shortcut_button.click()
        return True


class MigrationErrorDialog:
    """"Something went wrong" -- a fatal engine-side error during migration prep/transfer
    (e.g. "error 2969": confirmed via a live log, "Engine reported error 2969 on
    MigrationStatus (Status=false) after pairing -> FailurePage"). Confirmed from a
    user-supplied screenshot (2026-10-08) appearing layered over the transfer-progress
    screen, with that screen's own content ("0 B/s", "...minutes left") still visible,
    greyed out, behind it.

    Treated as an immediate, unrecoverable migration failure -- no accept()/close()
    method here, unlike every other dialog in this module. Those are all meant to be
    clicked through so the flow can continue; this one means the whole run should stop
    and raise, so callers check is_showing() and raise their own error immediately
    (see flows/target/transfer_flow.py), using read_error_text() to surface the real
    error code instead of a generic timeout message.
    """

    def __init__(self, app_session):
        self._heading = BaseComponent(app_session, *MIGRATION_ERROR_HEADING_LOCATOR, "MigrationErrorHeading")
        self._body = BaseComponent(app_session, *MIGRATION_ERROR_BODY_LOCATOR, "MigrationErrorBody")

    def is_showing(self, timeout: float = 0.1) -> bool:
        return self._heading.exists(timeout=timeout)

    def read_error_text(self, timeout: float = 2.0) -> str:
        """Best-effort: returns the body text (e.g. "Something went wrong while getting
        your PCs ready (error 2969). Please close and try again.") for a clearer
        failure message. Never raises -- evidence-gathering must never mask the real
        failure that's about to be raised by the caller."""
        try:
            return self._body.get_text(timeout=timeout)
        except Exception:
            return "(error text unavailable)"


class MigrationPreparationTransition:
    """Confirmed via user-supplied screenshots (2026-10-05): between OTP submission (or
    the "Welcome back" screen's Get Started button) and the trust-network dialog, the app
    passes through one or more transitional screens that span the manual Windows UAC
    approval (UAC runs on the secure desktop, categorically invisible to UI Automation --
    there's no API-level way to see or click it). Confirmed order: "Test, <name>, we're
    getting things ready" / "We're checking your PC to make sure your files and settings
    are ready for the move" first, then "Starting the migration assistant -- this only
    takes a moment" second.

    Not every run necessarily shows both, and exact timing relative to UAC can vary, so
    rather than requiring one exact screen, this polls the raw page source (one /source
    call per iteration, not a per-candidate locator lookup) for ANY of the known
    transition phrases -- the concrete, pollable signal that UAC was approved and
    something moved forward, instead of blindly waiting on one specific screen with no
    visibility into progress.
    """

    def __init__(self, app_session):
        self._session = app_session

    def wait_until_any_showing(self, timeout: float, poll_interval: float = 1.0) -> Optional[str]:
        """Returns the matched phrase once any of them appears within timeout, or None
        if the timeout expires first.
        """
        deadline = time.monotonic() + timeout
        while True:
            try:
                source = self._session.page_source.lower()
            except Exception:
                source = ""
            for text in TRANSITION_PHRASES:
                if text in source:
                    return text
            if time.monotonic() >= deadline:
                return None
            time.sleep(poll_interval)
