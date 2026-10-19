"""Target PC (MyDellExperience) transition table -- the data form of
TARGET_STATE_MACHINE.md. One State per screen/overlay/close prompt, each pointing at the
assertions module that detects it and the components class that acts on it.

Detection: every State carries a TextMatch (for SnapshotObserver) built from the same
text constants the assertions modules use, and a probe (the assertions module's
is_showing) for ProbeObserver. Both say "this is showing"; neither clicks.

Actions: thin lambdas over components/target/* methods, plus the few composite actions
that need more than one click (browser sign-in, pairing-code lookup, peer sync).

Naming follows the React screen/overlay ids in rebit's web/src/App.tsx so a future
log-based observer can map 1:1 (welcome, checkPrerequisites, connectOldPc, enterCode,
readyToMove, chooseWhatToMove, migrating, resultsSummary, complete, skippedFiles,
migrationDone, learnAboutErase; overlays trustNetwork, closeApplications, ...).

Verified against rebit source at a7ed19282, not live (2026-10-19).
"""

from __future__ import annotations

import time

import requests

from assertions.target import (
    cancel_migration_confirm_modal,
    choose_what_to_move_screen,
    close_apps_dialog,
    complete_screen,
    confirm_accounts_dialog,
    connection_lost_dialog,
    deferral_success_screen,
    desktop_shortcut_dialog,
    drive_mapping_modal,
    feedback_modal,
    install_browsers_to_migrate_bookmarks_dialog,
    learn_about_erase_screen,
    migration_cancelled_dialog,
    migration_complete_screen,
    migration_error_dialog,
    migration_summary_screen,
    network_disconnected_dialog,
    no_device_found_modal,
    not_admin_dialog,
    other_pc_network_disconnected_dialog,
    pairing_code_entry_screen,
    pairing_discovery_screen,
    plug_into_ac_power_dialog,
    ready_to_move_screen,
    regional_settings_not_supported_dialog,
    sign_in_failed_dialog,
    sign_in_launching_modal,
    sign_in_waiting_modal,
    sign_out_modal,
    skipped_files_screen,
    transfer_progress_screen,
    transfer_receive_screen,
    trust_network_dialog,
    welcome_deferral_error_screen,
    welcome_deferral_screen,
    welcome_screen,
)
from components.target.app_window import AppWindow
from components.target.cancel_migration_confirm_modal import CancelMigrationConfirmModal
from components.target.choose_what_to_move_screen import ChooseWhatToMoveScreen
from components.target.common_dialogs import (
    CloseAppsDialog,
    DesktopShortcutDialog,
    InstallBrowsersToMigrateBookmarksDialog,
    MigrationErrorDialog,
    NetworkDisconnectedDialog,
    OtherPcNetworkDisconnectedDialog,
    PlugIntoAcPowerDialog,
    RegionalSettingsNotSupportedDialog,
    SignInFailedDialog,
    SignInWaitingModal,
    TrustNetworkDialog,
)
from components.target.complete_screen import CompleteScreen
from components.target.connection_lost_dialog import ConnectionLostDialog
from components.target.deferral_success_screen import DeferralSuccessScreen
from components.target.drive_mapping_modal import DriveMappingModal
from components.target.feedback_modal import FeedbackModal
from components.target.learn_about_erase_screen import LearnAboutEraseScreen
from components.target.migrating_screen import MigratingScreen
from components.target.migration_cancelled_dialog import MigrationCancelledDialog
from components.target.migration_complete_screen import MigrationCompleteScreen
from components.target.migration_summary_screen import MigrationSummaryScreen
from components.target.no_device_found_modal import NoDeviceFoundModal
from components.target.not_admin_dialog import NotAdminDialog
from components.target.pairing_code_entry_screen import (
    ConfirmAccountsDialog,
    PairingCodeEntryScreen,
)
from components.target.ready_to_move_screen import ReadyToMoveScreen
from components.target.sign_in_screen import WelcomeScreen
from components.target.sign_out_modal import SignOutModal
from components.target.skipped_files_screen import SkippedFilesScreen
from components.target.transfer_receive_screen import TransferReceiveScreen
from components.target.welcome_deferral_error_screen import WelcomeDeferralErrorScreen
from components.target.welcome_deferral_screen import WelcomeDeferralScreen
from components.target.welcome_links import WelcomeLinks
from factory.session import find_new_browser_window_hwnd
from flows.target.authentication.sign_in_flow import SignInFlow
from orchestration.statemachine.model import Action, Model, State, TextMatch
from orchestration.statemachine.peer import (
    SOURCE_STATE_KEY,
    TARGET_STATE_KEY,
    attach_peer_actions,
    wait_for_peer_state,
)
from orchestration.statemachine.peer import (
    publish as _publish,
)
from utils.coordination_client import PAIRING_CODE_KEY

PAIRING_ATTEMPTS_DEFAULT = 5
PAIRING_CONFIRM_SECONDS = 30.0   # how long a typed code may sit in "Verifying..." before it counts as rejected
PAIRING_LOCK_POLL_SECONDS = 5.0


def snapshot_stale_pairing_code(ctx) -> None:
    """Remembers any pairing code already on the coordination service when this run
    starts so type_code() never types it. Confirmed live (2026-10-20): a reused
    --run-id handed the Target the PREVIOUS run's code within 80 ms; the app rejected
    it and the step sat on the code screen until it timed out."""
    tried = ctx.scratch.setdefault("tried_pairing_codes", set())
    try:
        stale = ctx.coordination.wait_for(ctx.run_id, PAIRING_CODE_KEY, timeout=1.0)
    except (TimeoutError, requests.exceptions.RequestException):
        return  # nothing published yet, or the service is not reachable -- nothing to exclude
    if stale:
        tried.add(str(stale))
        ctx.log.warning(f"pairing code {stale} was already on the coordination service for run {ctx.run_id} "
                        "-- treating it as stale; waiting for the Source to publish a new one")


def _fresh_pairing_code(ctx, exclude: set, deadline: float) -> str:
    """The next published code that is not in `exclude` (stale or already rejected)."""
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"no new pairing code appeared (excluding {sorted(exclude)})")
        try:
            value = str(ctx.coordination.wait_for(ctx.run_id, PAIRING_CODE_KEY, timeout=min(10.0, max(1.0, remaining))))
        except TimeoutError:
            continue
        if value not in exclude:
            return value
        time.sleep(2.0)


def _code_accepted(ctx, confirm: float) -> bool:
    """After typing a code: True once the code-entry heading is gone (paired, or the
    1 s success state), False as soon as the app shows the rejection message
    (confirmed via screenshot 2026-10-20: "That code didn't match. Check your old PC
    and try again.") or when `confirm` seconds pass with neither."""
    from assertions.target import pairing_code_entry_screen as code_assertions
    deadline = time.monotonic() + confirm
    while time.monotonic() < deadline:
        if not code_assertions.is_showing(ctx.app, timeout=0.5):
            return True
        if code_assertions.is_rejected_showing(ctx.app, timeout=0.5):
            ctx.log.warning("app says the code did not match")
            return False
    return False


def _wait_while_locked(ctx, deadline: float) -> None:
    from assertions.target import pairing_code_entry_screen as code_assertions
    logged = False
    while code_assertions.is_locked_showing(ctx.app, timeout=0.5):
        if not logged:
            ctx.log.warning("code entry is locked (too many wrong attempts) -- waiting for the countdown")
            logged = True
        if time.monotonic() >= deadline:
            raise TimeoutError("code entry stayed locked until the step timed out")
        time.sleep(PAIRING_LOCK_POLL_SECONDS)

BROWSER_OPEN_TIMEOUT_SECONDS = 45.0
PDF_OPEN_WAIT_SECONDS = 5.0
WRONG_PAIRING_CODE = "000000"


# ----------------------------------------------------------------------------- helpers

def _wait_for_new_browser(ctx, timeout: float = BROWSER_OPEN_TIMEOUT_SECONDS) -> None:
    known = ctx.scratch.get("known_hwnds", set())
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if find_new_browser_window_hwnd(known) is not None:
            return
        time.sleep(0.5)
    raise TimeoutError(f"no sign-in browser window appeared within {timeout:.0f}s")


def _sign_in_flow(ctx) -> SignInFlow:
    return SignInFlow(
        ctx.session,
        ctx.require_env("DDA_TARGET_SIGNIN_USERNAME"),
        ctx.require_env("DDA_TARGET_SIGNIN_PASSWORD"),
        ctx.require_env("DDA_TARGET_OTP_STATIC_VALUE"),
    )


# ----------------------------------------------------------------------------- model

def build(app_session) -> Model:
    """app_session may be None for validation -- components only touch it when an
    action actually runs."""
    welcome = WelcomeScreen(app_session)
    welcome_links = WelcomeLinks(app_session)
    deferral = WelcomeDeferralScreen(app_session)
    deferral_success = DeferralSuccessScreen(app_session)
    deferral_error = WelcomeDeferralErrorScreen(app_session)
    sign_in_waiting = SignInWaitingModal(app_session)
    sign_in_failed = SignInFailedDialog(app_session)
    sign_out = SignOutModal(app_session)
    trust = TrustNetworkDialog(app_session)
    code_entry = PairingCodeEntryScreen(app_session)
    no_device = NoDeviceFoundModal(app_session)
    accounts = ConfirmAccountsDialog(app_session)
    ready_to_move = ReadyToMoveScreen(app_session)
    choose = ChooseWhatToMoveScreen(app_session)
    transfer_ready = TransferReceiveScreen(app_session)
    drive_mapping = DriveMappingModal(app_session)
    close_apps = CloseAppsDialog(app_session)
    install_browsers = InstallBrowsersToMigrateBookmarksDialog(app_session)
    migrating = MigratingScreen(app_session)
    cancel_confirm = CancelMigrationConfirmModal(app_session)
    summary = MigrationSummaryScreen(app_session)
    complete = CompleteScreen(app_session)
    skipped = SkippedFilesScreen(app_session)
    done = MigrationCompleteScreen(app_session)
    feedback = FeedbackModal(app_session)
    erase_info = LearnAboutEraseScreen(app_session)
    not_admin = NotAdminDialog(app_session)
    battery = PlugIntoAcPowerDialog(app_session)
    no_network = NetworkDisconnectedDialog(app_session)
    other_pc_no_network = OtherPcNetworkDisconnectedDialog(app_session)
    connection_lost = ConnectionLostDialog(app_session)
    migration_cancelled = MigrationCancelledDialog(app_session)
    regional = RegionalSettingsNotSupportedDialog(app_session)
    failure = MigrationErrorDialog(app_session)
    shortcut = DesktopShortcutDialog(app_session)
    app_window = AppWindow(app_session)

    def click(method, *expect, name=None, description=""):
        return Action(name or method.__name__, lambda ctx, args: method(), expect=expect, description=description)

    def announce(state_name: str) -> Action:
        return Action("announce", lambda ctx, args: _publish(ctx, TARGET_STATE_KEY, state_name), idempotent=False,
                      description=f"publish target_state={state_name} for the Source script")

    def wait_for_source(ctx, args) -> None:
        wait_for_peer_state(ctx, SOURCE_STATE_KEY, str(args["state"]), float(args.get("timeout", 600.0)))

    wait_for_source_action = Action("wait_for_source", wait_for_source,
                                    description="block until the Source script published source_state=<state>")

    # -- composite actions -------------------------------------------------------
    def welcome_continue(ctx, args) -> None:
        if "tried_pairing_codes" not in ctx.scratch:
            snapshot_stale_pairing_code(ctx)  # once per run, before any pairing happens
        # the browser-window snapshot MUST precede the click (factory/session.py)
        ctx.scratch["known_hwnds"] = ctx.session.snapshot_browser_windows()
        welcome.click_sign_in()

    def browser_sign_in(ctx, args) -> None:
        _wait_for_new_browser(ctx)
        _sign_in_flow(ctx).browser_authenticate(
            ctx.scratch.get("known_hwnds", set()),
            step_timeout=float(args.get("step_timeout", 20.0)),
            negative_check=bool(args.get("negative_check", False)),
        )

    def sign_in_retry(ctx, args) -> None:
        ctx.scratch["known_hwnds"] = ctx.session.snapshot_browser_windows()
        sign_in_failed.click_retry()
        browser_sign_in(ctx, args)

    def sign_in_retry_link(ctx, args) -> None:
        ctx.scratch["known_hwnds"] = ctx.session.snapshot_browser_windows()
        sign_in_waiting.click_retry()
        browser_sign_in(ctx, args)

    def type_code(ctx, args) -> None:
        """Types the Source's pairing code and retries on rejection.

        args: code (explicit, no retries), timeout (overall, default 600 s), attempts
        (default 5), confirm_timeout (default 30 s). A code counts as accepted when the
        code-entry heading goes away within confirm_timeout; otherwise the next
        published code (never one already tried, nor one that predates this run -- see
        snapshot_stale_pairing_code) is typed, after any lockout countdown has run."""
        explicit = args.get("code")
        attempts = 1 if explicit else int(args.get("attempts", PAIRING_ATTEMPTS_DEFAULT))
        confirm = float(args.get("confirm_timeout", PAIRING_CONFIRM_SECONDS))
        deadline = time.monotonic() + float(args.get("timeout", 600.0))
        tried = ctx.scratch.setdefault("tried_pairing_codes", set())

        for attempt in range(1, attempts + 1):
            code = str(explicit) if explicit else _fresh_pairing_code(ctx, tried, deadline)
            _wait_while_locked(ctx, deadline)
            ctx.log.info(f"typing pairing code {code} (attempt {attempt}/{attempts})")
            code_entry.enter_code(code)
            tried.add(code)
            if _code_accepted(ctx, confirm):
                ctx.log.success(f"pairing code {code} accepted")
                return
            ctx.log.warning(f"pairing code {code} was not accepted within {confirm:.0f}s")
        raise RuntimeError(f"pairing code rejected {attempts} time(s); tried {sorted(tried)}")

    def type_wrong_code(ctx, args) -> None:
        code_entry.enter_code(str(args.get("code", WRONG_PAIRING_CODE)))

    def download_pdf(ctx, args) -> None:
        done.click_download_pdf_link()
        time.sleep(float(args.get("wait", PDF_OPEN_WAIT_SECONDS)))

    def open_pdf(ctx, args) -> None:
        complete.click_open_pdf()
        time.sleep(float(args.get("wait", PDF_OPEN_WAIT_SECONDS)))

    def read_failure_text(ctx, args) -> str:
        return (failure.read_title() + " -- " + failure.read_error_text()).strip(" -")

    def submit_feedback(ctx, args) -> None:
        feedback.set_rating(float(args.get("rating", 5)))
        comment = args.get("comment")
        if comment:
            feedback.type_comment(str(comment))
        feedback.click_submit()

    def select_reminder(ctx, args) -> None:
        deferral.select_option(str(args.get("option", "tonight")))

    m = Model(role="target")

    # ============================================================== SCREENS
    m.add(State(
        "welcome", "screen", "user",
        text=TextMatch(any=("make this dell yours", "welcome back"), none=("sign in or create an account",)),
        probe=welcome_screen.is_showing,
        next=("checkPrerequisites",),
        actions={
            "continue": Action("continue", welcome_continue, expect=("checkPrerequisites", "signIn", "welcome")),
            "remind_me_later": click(welcome_links.click_remind_me_later, "welcomeDeferral", name="remind_me_later"),
            "sign_out": click(welcome_links.click_sign_out, "welcomeSignedOut", name="sign_out"),
            "announce": announce("welcome"),
        },
        description="Welcome / Welcome back (entitled, signed in or cached login)",
    ))
    m.add(State(
        "welcomeSignedOut", "screen", "user",
        text=TextMatch(all=("sign in or create an account",)),
        probe=welcome_screen.is_signed_out_showing, priority=5,
        actions={"continue": Action("continue", welcome_continue, expect=("signIn", "signInLaunching", "checkPrerequisites"))},
        description="Welcome with no cached login -- Continue opens the sign-in modal",
    ))
    m.add(State(
        "welcomeDeferral", "screen", "user",
        text=TextMatch(all=(welcome_deferral_screen.HEADING_CONTAINS_TEXT,)),
        probe=welcome_deferral_screen.is_showing,
        actions={
            "select_option": Action("select_option", select_reminder),
            "set_reminder": click(deferral.click_set_reminder, "deferralSuccess", "welcomeDeferralError", name="set_reminder"),
            "close": click(deferral.click_close, "welcome", name="close"),
        },
    ))
    m.add(State(
        "deferralSuccess", "screen", "user",
        text=TextMatch(all=("got it", "send you a notification")),
        probe=deferral_success_screen.is_showing,
        actions={"close": click(deferral_success.click_close, "welcome", name="close")},
    ))
    m.add(State(
        "welcomeDeferralError", "screen", "user",
        text=TextMatch(all=(welcome_deferral_error_screen.HEADING_CONTAINS_TEXT,)),
        probe=welcome_deferral_error_screen.is_showing,
        actions={"close": click(deferral_error.click_close, "welcome", name="close")},
    ))
    m.add(State(
        "checkPrerequisites", "screen", "waiting",
        text=TextMatch(any=("getting things ready", "checking your pc")),
        next=("connectOldPc",),
        actions={"cancel": Action("cancel", lambda ctx, args: ready_to_move.click_cancel(), expect=("welcome",))},
        description="engine launch + PreCheck.Migration; no timeout in the app (already-paired -> readyToMove "
                    "exists in the backend but needs a retained session, which every Cancel/Stop resets)",
    ))
    m.add(State(
        "connectOldPc", "screen", "peer",
        text=TextMatch(all=(pairing_discovery_screen.HEADING_CONTAINS_TEXT,)),
        probe=pairing_discovery_screen.is_showing,
        next=("enterCode", "readyToMove"),
        actions={
            "cancel": Action("cancel", lambda ctx, args: ready_to_move.click_cancel(), expect=("welcome",)),
            "announce": announce("connectOldPc"),
            "wait_for_source": wait_for_source_action,
        },
    ))
    m.add(State(
        "enterCode", "screen", "peer",
        text=TextMatch(all=("connect your two pcs",), none=("too many wrong attempts",)),
        probe=pairing_code_entry_screen.is_showing,
        next=("enterCodeSuccess", "readyToMove", "enterCodeLocked", "connectOldPc"),
        actions={
            "type_code": Action("type_code", type_code, expect=("enterCodeSuccess", "readyToMove", "enterCode"), idempotent=False),
            "type_wrong_code": Action("type_wrong_code", type_wrong_code, expect=("enterCode", "enterCodeLocked"), idempotent=False),
            "cancel": click(code_entry.click_cancel, "welcome", name="cancel"),
            "announce": announce("enterCode"),
        },
    ))
    m.add(State(
        "enterCodeLocked", "screen", "waiting",
        text=TextMatch(all=(pairing_code_entry_screen.LOCKED_STATUS_CONTAINS_TEXT,)),
        probe=pairing_code_entry_screen.is_locked_showing, priority=5,
        next=("enterCode",),
        actions={"cancel": click(code_entry.click_cancel, "welcome", name="cancel")},
        description="3 wrong codes -> read-only with a countdown; unlocks on its own",
    ))
    m.add(State(
        "enterCodeSuccess", "screen", "waiting",
        text=TextMatch(any=("great, you're connected", "connection successful")),
        probe=pairing_code_entry_screen.is_connection_successful_showing, priority=5,
        next=("readyToMove",),
        description="1 s success state before readyToMove",
    ))
    m.add(State(
        "readyToMove", "screen", "waiting",
        text=TextMatch(all=(ready_to_move_screen.HEADING_CONTAINS_TEXT,)),
        probe=ready_to_move_screen.is_showing,
        next=("chooseWhatToMove",),   # 'everything' is the default on every fresh visit (ChooseWhatToMovePageViewModel.cs:685)
        actions={"cancel": click(ready_to_move.click_cancel, "welcome", name="cancel"),
                 "announce": announce("readyToMove")},
        description="Compatibility.Migration then MigrationInfo.Init/Details",
    ))
    m.add(State(
        "chooseWhatToMove", "screen", "user",
        text=TextMatch(all=(transfer_receive_screen.HEADING_CONTAINS_TEXT,)),
        probe=transfer_receive_screen.wait_until_showing,
        actions={
            "migrate_now": click(transfer_ready.start_transfer, "migrating", name="migrate_now"),
            "let_me_choose": click(choose.click_let_me_choose, "chooseFiles", name="let_me_choose"),
            "change_drive": click(choose.click_change_drive, name="change_drive"),
            "cancel": click(choose.click_cancel, "welcome", name="cancel"),
            "announce": announce("chooseWhatToMove"),
            "wait_for_source": wait_for_source_action,
        },
        description="'everything' mode: We're ready to transfer your files",
    ))
    m.add(State(
        "chooseFiles", "screen", "user",
        text=TextMatch(all=(choose_what_to_move_screen.HEADING_TEXT,)),
        probe=choose_what_to_move_screen.is_showing,
        actions={
            "select_all": click(choose.click_select_all, name="select_all"),
            "go_back": click(choose.click_go_back, "chooseWhatToMove", name="go_back"),
            "migrate_now": click(transfer_ready.start_transfer, "migrating", name="migrate_now"),
            "change_drive": click(choose.click_change_drive, name="change_drive"),
            "cancel": click(choose.click_cancel, "welcome", name="cancel"),
        },
        description="'Let me choose' tree mode: Tell us what you want to transfer",
    ))
    m.add(State(
        "migrating", "screen", "waiting",
        text=TextMatch(all=(transfer_progress_screen.HEADING_CONTAINS_TEXT,)),
        probe=transfer_progress_screen.is_showing,
        next=("resultsSummaryLoading", "resultsSummary"),
        actions={
            "cancel": click(migrating.click_cancel, name="cancel"),
            "close_window": click(app_window.click_close, name="close_window"),
            "announce": announce("migrating"),
            "wait_for_source": wait_for_source_action,
        },
    ))
    m.add(State(
        "resultsSummaryLoading", "screen", "waiting",
        text=TextMatch(any=("preparing your transfer details", "cancelling your transfer")),
        next=("resultsSummary",), priority=5,
        description="Migration.Report in flight (150 s cap in the app)",
    ))
    m.add(State(
        "resultsSummary", "screen", "user",
        text=TextMatch(all=(migration_summary_screen.HEADING_TEXT,), none=("back to summary",)),
        probe=migration_summary_screen.is_showing,
        actions={
            "finish": click(summary.click_finish, "migrationDone", "welcome", name="finish"),
            "view_details": click(summary.click_view_the_details, "complete", "skippedFiles", name="view_details"),
            "close_window": click(app_window.click_close, name="close_window"),
            "announce": announce("resultsSummary"),
        },
    ))
    m.add(State(
        "complete", "screen", "user",
        text=TextMatch(all=(complete_screen.HEADING_TEXT, "back to summary")),
        probe=complete_screen.is_showing, priority=5,
        actions={
            "back_to_summary": click(complete.click_back_to_summary, "resultsSummary", name="back_to_summary"),
            "open_pdf": Action("open_pdf", open_pdf),
        },
    ))
    m.add(State(
        "skippedFiles", "screen", "user",
        text=TextMatch(all=(skipped_files_screen.HEADING_CONTAINS_TEXT,)),
        probe=skipped_files_screen.is_showing,
        actions={
            "retry": click(skipped.click_retry, "migrating", name="retry"),
            "finish": click(skipped.click_finish, "migrationDone", "welcome", name="finish"),
            "go_to_summary": click(skipped.click_go_to_summary, "migrationDone", "welcome", name="go_to_summary"),
        },
    ))
    m.add(State(
        "migrationDone", "screen", "user",
        text=TextMatch(all=(migration_complete_screen.HEADING_TEXT,)),
        probe=migration_complete_screen.is_showing,
        actions={
            "download_pdf": Action("download_pdf", download_pdf),
            "view_summary": click(done.click_view_summary, "resultsSummary", name="view_summary"),
            "tell_us_how_we_did": click(done.click_tell_us_how_we_did, name="tell_us_how_we_did"),
            "transfer_more_data": click(done.click_transfer_more_data, "welcome", name="transfer_more_data"),
            "erase_old_pc": click(done.click_erase_old_pc, "learnAboutErase", name="erase_old_pc"),
            "close": click(done.click_close, name="close"),
            "close_window": click(app_window.click_close, name="close_window"),
            "announce": announce("migrationDone"),
        },
    ))
    m.add(State(
        "learnAboutErase", "screen", "user",
        text=TextMatch(all=(learn_about_erase_screen.HEADING_TEXT,)),
        probe=learn_about_erase_screen.is_showing,
        actions={"back_to_home": click(erase_info.click_back_to_home, "welcome", name="back_to_home")},
    ))

    # ============================================================== OVERLAYS
    m.add(State(
        "signIn", "overlay",
        text=TextMatch(all=(sign_in_waiting_modal.HEADING_TEXT,)),
        probe=sign_in_waiting_modal.is_showing,
        actions={
            "sign_in": Action("sign_in", browser_sign_in, expect=("signInLaunching", "checkPrerequisites", "signInFailed", "welcome"), idempotent=False),
            "retry": Action("retry", sign_in_retry_link, expect=("signInLaunching", "checkPrerequisites", "signInFailed"), idempotent=False),
            "cancel": click(sign_in_waiting.click_cancel, "welcomeSignedOut", "welcome", name="cancel"),
        },
        description="waiting view: browser is open for the Dell sign-in",
    ))
    m.add(State(
        "signInLaunching", "overlay",
        text=TextMatch(all=(sign_in_launching_modal.HEADING_CONTAINS_TEXT,)),
        probe=sign_in_launching_modal.is_showing, auto_recovers=True, priority=5,
        description="browser callback received; engine starting -- clears on its own",
    ))
    m.add(State(
        "signInFailed", "overlay",
        text=TextMatch(any=("sign you in", "problem signing in")),
        probe=sign_in_failed_dialog.is_showing, priority=6,
        actions={
            "retry": Action("retry", sign_in_retry, expect=("signInLaunching", "checkPrerequisites", "signInFailed"), idempotent=False),
            "cancel": click(sign_in_waiting.click_cancel, "welcomeSignedOut", "welcome", name="cancel"),
        },
    ))
    m.add(State(
        "signOut", "overlay",
        text=TextMatch(all=(sign_out_modal.HEADING_CONTAINS_TEXT,)),
        probe=sign_out_modal.is_showing, auto_recovers=True,
        actions={"cancel": click(sign_out.click_cancel, name="cancel")},
    ))
    m.add(State(
        "signOutError", "overlay",
        text=TextMatch(all=(sign_out_modal.ERROR_HEADING_TEXT,)),
        probe=sign_out_modal.is_error_showing, priority=5,
        actions={"retry": click(sign_out.click_retry, name="retry"),
                 "cancel": click(sign_out.click_cancel, name="cancel")},
    ))
    m.add(State(
        "trustNetwork", "overlay",
        # Confirmed live (2026-10-20): the other-PC-offline body ("Reconnect to a trusted
        # network to continue") CONTAINS this heading, so the heading alone misfired; the
        # trust dialog is the only one whose body says "recognize and trust".
        text=TextMatch(all=(trust_network_dialog.HEADING_TEXT, "recognize and trust")),
        probe=trust_network_dialog.is_showing,
        actions={"trust_network": click(trust.click_trust_network, name="trust_network"),
                 "cancel": click(trust.click_cancel, "welcome", name="cancel")},
    ))
    m.add(State(
        "noDeviceFound", "overlay",
        text=TextMatch(all=(no_device_found_modal.HEADING_CONTAINS_TEXT,)),
        probe=no_device_found_modal.is_showing,
        actions={"cancel_transfer": click(no_device.click_cancel_transfer, "welcome", name="cancel_transfer")},
        description="engine 2500 after 10 min of discovery; repeatable",
    ))
    m.add(State(
        "accountMismatch", "overlay",
        text=TextMatch(all=(confirm_accounts_dialog.HEADING_CONTAINS_TEXT,)),
        probe=confirm_accounts_dialog.is_showing,
        actions={"continue": click(accounts.click_continue, name="continue"),
                 "cancel_transfer": click(accounts.click_cancel_transfer, "welcome", name="cancel_transfer")},
    ))
    m.add(State(
        "closeApplications", "overlay",
        text=TextMatch(all=(close_apps_dialog.HEADING_TEXT,), none=(close_apps_dialog.ERROR_HEADING_TEXT,)),
        probe=close_apps_dialog.is_showing,
        actions={"close_applications": click(close_apps.click_close_application, name="close_applications"),
                 "cancel_transfer": click(close_apps.click_cancel_transfer, name="cancel_transfer")},
    ))
    m.add(State(
        "closeApplicationsFailed", "overlay",
        text=TextMatch(all=(close_apps_dialog.ERROR_HEADING_TEXT,)),
        probe=close_apps_dialog.is_failed_attempt_showing, priority=5,
        actions={"retry": click(close_apps.click_retry, name="retry"),
                 "check_again": click(close_apps.click_check_again, name="check_again")},
        description="a close attempt failed: Check again / Retry",
    ))
    m.add(State(
        "installBrowser", "overlay",
        text=TextMatch(all=(install_browsers_to_migrate_bookmarks_dialog.HEADING_CONTAINS_TEXT,)),
        probe=install_browsers_to_migrate_bookmarks_dialog.is_showing,
        actions={"skip": click(install_browsers.click_skip, name="skip"),
                 "resume": click(install_browsers.click_resume, name="resume")},
    ))
    m.add(State(
        "driveMapping", "overlay",
        text=TextMatch(all=(drive_mapping_modal.HEADING_CONTAINS_TEXT, "we found")),
        probe=drive_mapping_modal.is_showing,
        actions={"apply": click(drive_mapping.click_apply, name="apply"),
                 "rescan": click(drive_mapping.click_rescan, name="rescan"),
                 "cancel": click(drive_mapping.click_cancel, name="cancel")},
    ))
    m.add(State(
        "feedbackModal", "overlay",
        text=TextMatch(all=(feedback_modal.BODY_CONTAINS_TEXT,)),
        probe=feedback_modal.is_showing,
        actions={"submit": Action("submit", submit_feedback, idempotent=False),
                 "cancel": click(feedback.click_cancel, name="cancel")},
    ))
    m.add(State(
        "notAdmin", "overlay",
        text=TextMatch(all=(not_admin_dialog.HEADING_TEXT,)),
        probe=not_admin_dialog.is_showing,
        actions={"cancel_transfer": click(not_admin.click_cancel_transfer, "welcome", name="cancel_transfer")},
    ))
    m.add(State(
        "batteryCritical", "overlay",
        text=TextMatch(all=(plug_into_ac_power_dialog.HEADING_TEXT,)),
        probe=plug_into_ac_power_dialog.is_showing, auto_recovers=True,
        actions={"cancel_transfer": click(battery.click_cancel, "welcome", name="cancel_transfer")},
        description="AC poll every 3 s; clears on its own when plugged in",
    ))
    m.add(State(
        "noNetwork", "overlay",
        text=TextMatch(all=(network_disconnected_dialog.HEADING_TEXT,)),
        probe=network_disconnected_dialog.is_showing, auto_recovers=True, priority=5,
        actions={"cancel_transfer": click(no_network.cancel_transfer, "welcome", name="cancel_transfer")},
        description="this PC offline; clears on reconnect (Network.Status 2507 / 3 s OS poll)",
    ))
    m.add(State(
        "otherPcNoNetwork", "overlay",
        text=TextMatch(all=(other_pc_network_disconnected_dialog.HEADING_TEXT,)),
        probe=other_pc_network_disconnected_dialog.is_showing, auto_recovers=True, priority=5,
        actions={"cancel_transfer": click(other_pc_no_network.cancel_transfer, "welcome", name="cancel_transfer")},
        description="other PC offline; clears on reconnect",
    ))
    m.add(State(
        "connectionLost", "overlay",
        text=TextMatch(all=("we lost the connection to your other pc",)),
        probe=connection_lost_dialog.is_showing,
        actions={"try_again": click(connection_lost.click_try_again, "enterCode", "readyToMove", name="try_again"),
                 "cancel_transfer": click(connection_lost.click_cancel_transfer, name="cancel_transfer")},
        description="only after two consecutive engine-channel errors",
    ))
    m.add(State(
        "migrationCancelled", "overlay",
        text=TextMatch(all=(migration_cancelled_dialog.HEADING_CONTAINS_TEXT,)),
        probe=migration_cancelled_dialog.is_showing,
        actions={"try_again": click(migration_cancelled.click_try_again, "connectOldPc", name="try_again")},
        description="old PC cancelled before Migration.Start",
    ))
    m.add(State(
        "localeMismatch", "overlay", "terminal",
        text=TextMatch(all=(regional_settings_not_supported_dialog.HEADING_TEXT,)),
        actions={"close": click(regional.click_close, name="close")},
    ))
    m.add(State(
        "localeNotSupported", "overlay", "terminal",
        text=TextMatch(all=(regional_settings_not_supported_dialog.LOCATION_NOT_SUPPORTED_CONTAINS_TEXT,)),
        actions={"close": click(regional.click_close, name="close")},
    ))
    m.add(State(
        "failure", "overlay", "terminal",
        text=TextMatch(any=(
            migration_error_dialog.HEADING_TEXT,
            migration_error_dialog.ERASE_STARTED_ON_OLD_PC_HEADING_TEXT,
            migration_error_dialog.UPDATE_DDA_HEADING_TEXT,
            migration_error_dialog.UPDATE_SUPPORTASSIST_HEADING_TEXT,
        )),
        probe=migration_error_dialog.is_any_failure_showing, priority=-5,
        actions={
            "read_text": Action("read_text", read_failure_text),
            "close": click(failure.click_close, name="close"),
            "ok": click(failure.click_ok, "welcome", "resultsSummary", name="ok"),
            "cancel_transfer": click(failure.click_cancel_transfer, name="cancel_transfer"),
        },
        description="Something went wrong / erase started / version mismatch",
    ))

    # ============================================================== CLOSE PROMPTS
    m.add(State(
        "cancelMigrationConfirm", "close_prompt",
        text=TextMatch(all=(cancel_migration_confirm_modal.HEADING_TEXT,)),
        probe=cancel_migration_confirm_modal.is_showing,
        actions={"yes_cancel": click(cancel_confirm.click_yes_cancel, "resultsSummaryLoading", "resultsSummary", name="yes_cancel"),
                 "no_continue": click(cancel_confirm.click_no_continue, "migrating", name="no_continue")},
    ))
    m.add(State(
        "desktopShortcut", "close_prompt",
        text=TextMatch(all=(desktop_shortcut_dialog.HEADING_TEXT,)),
        probe=desktop_shortcut_dialog.is_showing,
        actions={"create_shortcut": click(shortcut.click_create_shortcut, name="create_shortcut"),
                 "no_thanks": click(shortcut.click_no_thanks, name="no_thanks")},
    ))

    attach_peer_actions(m, own_key=TARGET_STATE_KEY, peer_key=SOURCE_STATE_KEY)
    m.validate()
    return m
