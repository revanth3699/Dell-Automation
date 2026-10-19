"""Source PC (Dell Data Assistant, MigrateToDell.UI) transition table.

Simpler than the Target side: the Source only ever shows one WPF page at a time, with a
few dialogs layered on it. Texts come from the existing assertions/source modules
(single source of truth); actions wrap the existing components/source classes.

Screens:  welcome -> searching -> pairingCode -> linkedSuccess -> readyToMigrate ->
          migrating -> one of migrationComplete / migrationPartialTryAgain /
          migrationPartialSummary / migrationError / cancelledByOtherPc
Overlays: trustNetwork, batteryCritical, noNetwork, otherPcLost, regionalNotSupported
Prompt:   confirmCancel ("Are you sure you want to cancel?" / "...cancel migration?")

Verified against MigrateToDell.UI source (Resources.resx, Views/*.xaml), not live.
Where the Source app recovers on its own is marked [inferred] -- the WPF pages re-run
their precheck when the OS reports the network back (WelcomePageViewModel.cs:1045
"Network is connected. Sending Precheck again."), but this has not been watched live.
"""

from __future__ import annotations

import time

import requests

from assertions.source import (
    battery_critically_low_dialog,
    confirm_cancel_dialog,
    network_disconnected_dialog,
    other_pc_network_disconnected_dialog,
    pairing_code_screen,
    regional_settings_not_supported_dialog,
    searching_screen,
    transfer_progress_screen,
    trust_network_dialog,
    welcome_screen,
)
from components.source.battery_critically_low_dialog import BatteryCriticallyLowDialog
from components.source.confirm_cancel_dialog import ConfirmCancelDialog
from components.source.network_disconnected_dialog import NetworkDisconnectedDialog
from components.source.other_pc_network_disconnected_dialog import (
    OtherPcNetworkDisconnectedDialog,
)
from components.source.pairing_code_screen import PairingCodeScreen
from components.source.regional_settings_not_supported_dialog import (
    RegionalSettingsNotSupportedDialog,
)
from components.source.transfer_progress_screen import TransferProgressScreen
from components.source.trust_network_dialog import TrustNetworkDialog
from components.source.welcome_screen import WelcomeScreen
from flows.source.pairing_flow import CODE_REPUBLISH_INTERVAL_SECONDS
from orchestration.statemachine.model import Action, Model, State, TextMatch
from orchestration.statemachine.peer import (
    SOURCE_STATE_KEY,
    TARGET_STATE_KEY,
    attach_peer_actions,
    publish,
)
from utils.coordination_client import PAIRING_CODE_KEY


def _publish_state(ctx, value: str) -> None:
    """Lets the Target script wait on e.g. source_state == migrating."""
    publish(ctx, SOURCE_STATE_KEY, value)


def build(app_session) -> Model:
    """app_session may be None for validation only -- components are bound lazily
    (BaseComponent touches the session only when an action runs)."""
    welcome = WelcomeScreen(app_session)
    code_screen = PairingCodeScreen(app_session)
    progress = TransferProgressScreen(app_session)
    trust = TrustNetworkDialog(app_session)
    battery = BatteryCriticallyLowDialog(app_session)
    no_network = NetworkDisconnectedDialog(app_session)
    other_pc_lost = OtherPcNetworkDisconnectedDialog(app_session)
    regional = RegionalSettingsNotSupportedDialog(app_session)
    confirm_cancel = ConfirmCancelDialog(app_session)

    def click(method, *expect, description=""):
        return Action(method.__name__, lambda ctx, args: method(), expect=expect, description=description)

    def publish_code(ctx, args) -> None:
        """Reads the on-screen pairing code and publishes it to the coordination service,
        re-reading every CODE_REPUBLISH_INTERVAL_SECONDS (the code rotates) until the
        pairing-code screen is gone (Target paired) or args['timeout'] elapses."""
        timeout = float(args.get("timeout", 600.0))
        deadline = time.monotonic() + timeout
        last = None
        _publish_state(ctx, "pairingCode")
        while time.monotonic() < deadline:
            if not pairing_code_screen.is_showing(ctx.app, timeout=1.0):
                ctx.log.success("pairing-code screen gone -- Target has paired")
                return
            try:
                code = code_screen.read_code()
            except (RuntimeError, OSError, requests.exceptions.RequestException) as exc:
                ctx.log.warning(f"read_code() failed this cycle, retrying: {exc}")
                time.sleep(CODE_REPUBLISH_INTERVAL_SECONDS)
                continue
            if code != last:
                try:
                    ctx.coordination.publish(ctx.run_id, PAIRING_CODE_KEY, code)
                    ctx.log.success(f"published pairing code {code}")
                    last = code
                except requests.exceptions.RequestException as exc:
                    ctx.log.warning(f"publish failed this cycle, retrying: {exc}")
            time.sleep(CODE_REPUBLISH_INTERVAL_SECONDS)
        raise TimeoutError(f"Target did not pair within {timeout:.0f}s of publishing the code")

    def announce(state_name: str):
        return Action("announce", lambda ctx, args: _publish_state(ctx, state_name), expect=(),
                      description=f"publish source_state={state_name} for the Target script")

    m = Model(role="source")

    # ------------------------------------------------------------------ screens
    m.add(State("welcome", "screen", "user", text=TextMatch(all=("let's get started",)),
                probe=welcome_screen.is_showing,
                actions={"lets_get_started": click(welcome.click_get_started, "searching", "pairingCode")},
                next=()))
    m.add(State("searching", "screen", "peer", text=TextMatch(all=(searching_screen.HEADING_TEXT,)),
                probe=searching_screen.is_showing, next=("pairingCode",),
                actions={"announce": announce("searching")}))
    m.add(State("pairingCode", "screen", "peer", text=TextMatch(all=(pairing_code_screen.HEADING_TEXT,)),
                probe=pairing_code_screen.is_showing, next=("linkedSuccess", "readyToMigrate"),
                actions={
                    "publish_code": Action("publish_code", publish_code, expect=("linkedSuccess", "readyToMigrate")),
                    "cancel": Action("cancel", lambda ctx, args: code_screen.cancel(), expect=("welcome",)),
                }))
    m.add(State("linkedSuccess", "screen", "waiting",
                text=TextMatch(all=(transfer_progress_screen.LINKED_SUCCESS_HEADING_TEXT,)),
                probe=transfer_progress_screen.is_linked_success, next=("readyToMigrate", "migrating")))
    m.add(State("readyToMigrate", "screen", "peer",
                text=TextMatch(all=(transfer_progress_screen.READY_TO_MIGRATE_HEADING_TEXT,)),
                probe=transfer_progress_screen.is_ready_to_migrate,
                next=("migrating", "cancelledByOtherPc"),
                actions={"announce": announce("readyToMigrate"),
                         "cancel": click(progress.click_close, "confirmCancel")}))
    m.add(State("migrating", "screen", "peer",
                text=TextMatch(all=(transfer_progress_screen.MIGRATING_DATA_HEADING_TEXT,)),
                probe=transfer_progress_screen.is_migrating,
                next=("migrationComplete", "migrationPartialTryAgain", "migrationPartialSummary",
                      "migrationError", "cancelledByOtherPc"),
                actions={"announce": announce("migrating"),
                         "cancel": click(progress.click_close, "confirmCancel")}))
    m.add(State("migrationComplete", "screen", "user",
                text=TextMatch(all=(transfer_progress_screen.MIGRATION_COMPLETE_HEADING_TEXT,)),
                probe=transfer_progress_screen.is_migration_complete_confirmed,
                actions={"announce": announce("migrationComplete"),
                         "close": click(progress.click_close_after_delay)}))
    m.add(State("migrationPartialTryAgain", "screen", "user",
                text=TextMatch(all=(transfer_progress_screen.MIGRATION_PARTIAL_TRY_AGAIN_HEADING_TEXT,)),
                probe=transfer_progress_screen.is_migration_partial_try_again_confirmed,
                actions={"announce": announce("migrationPartialTryAgain"),
                         "try_again": click(progress.click_try_again, "searching", "pairingCode"),
                         "close": click(progress.click_close)}))
    m.add(State("migrationPartialSummary", "screen", "user",
                text=TextMatch(all=(transfer_progress_screen.MIGRATION_PARTIAL_SUMMARY_HEADING_TEXT,)),
                probe=transfer_progress_screen.is_migration_partial_summary_confirmed,
                next=("migrating",),   # Target may Retry the skipped files
                actions={"announce": announce("migrationPartialSummary"),
                         "close": click(progress.click_close)}))
    m.add(State("migrationError", "screen", "user",
                text=TextMatch(all=(transfer_progress_screen.MIGRATION_ERROR_HEADING_TEXT,)),
                probe=transfer_progress_screen.is_migration_error_confirmed,
                actions={"announce": announce("migrationError"),
                         "try_again": click(progress.click_try_again, "searching", "pairingCode"),
                         "close": click(progress.click_close)}))
    # resx CancelMigrationHeader "You've canceled migration on your {0}" -- shown when the
    # OTHER PC cancels. Text-only; no assertions module exists yet (snapshot observer only).
    m.add(State("cancelledByOtherPc", "screen", "user",
                text=TextMatch(all=("canceled migration on your",)),
                actions={"announce": announce("cancelledByOtherPc"),
                         "close": click(progress.click_close)}))

    # ------------------------------------------------------------------ overlays
    m.add(State("trustNetwork", "overlay", text=TextMatch(all=(trust_network_dialog.HEADING_CONTAINS_TEXT,)),
                probe=trust_network_dialog.is_showing,
                actions={"yes_continue": click(trust.click_yes_continue),
                         "cancel": Action("cancel", lambda ctx, args: code_screen.cancel())}))
    m.add(State("batteryCritical", "overlay", text=TextMatch(all=(battery_critically_low_dialog.HEADING_TEXT,)),
                probe=battery_critically_low_dialog.is_showing, auto_recovers=True,  # [inferred]
                actions={"cancel": click(battery.click_cancel, "confirmCancel")}))
    m.add(State("noNetwork", "overlay", text=TextMatch(all=("isn't connected to a network",)),
                probe=network_disconnected_dialog.is_showing, auto_recovers=True,  # [inferred]
                actions={"cancel": click(no_network.click_cancel, "confirmCancel")}))
    m.add(State("otherPcLost", "overlay",
                text=TextMatch(all=(other_pc_network_disconnected_dialog.HEADING_TEXT,)),
                probe=other_pc_network_disconnected_dialog.is_showing, auto_recovers=True,  # [inferred]
                actions={"cancel": click(other_pc_lost.click_cancel, "confirmCancel")}))
    m.add(State("regionalNotSupported", "overlay", "terminal",
                text=TextMatch(all=(regional_settings_not_supported_dialog.HEADING_CONTAINS_TEXT,)),
                probe=regional_settings_not_supported_dialog.is_showing,
                actions={"close": click(regional.click_close)}))

    # ------------------------------------------------------------------ close prompt
    # Matches both CancelGenericHeader "Are you sure you want to cancel?" and
    # CancelMigrationConfirmHeader "Are you sure you want to cancel migration?".
    m.add(State("confirmCancel", "close_prompt", text=TextMatch(all=("sure you want to cancel",)),
                probe=confirm_cancel_dialog.is_showing,
                actions={"no_dont_cancel": click(confirm_cancel.click_no_dont_cancel),
                         "yes_cancel_now": click(confirm_cancel.click_yes_cancel_now, "welcome")}))

    attach_peer_actions(m, own_key=SOURCE_STATE_KEY, peer_key=TARGET_STATE_KEY)
    m.validate()
    return m
