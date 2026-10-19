"""Watches for toast notifications using Windows' UserNotificationListener API (WinRT,
via the `winsdk` package), matches each new one against utils/notifications/rules.py's
configurable criteria (app identity and/or heading text), and -- on a match -- resumes
every currently-pending reminder (see state.py), each running its own recorded scenario
via orchestration/role_runner.py.

Per explicit user direction (2026-10-19): "event listener keeps an eye on toast
notification, event handler checks on condition (example: notification title), and then
triggers an automation flow." The condition-check lives in rules.py, kept separate from
this module's own polling mechanics, so a new rule can be added there without touching
this file -- and a different assigned scenario just needs its own pending state file
recording that scenario (see state.py), not a code change here either.

Confirmed live in this repo (no real Dell app available for the original research, now
confirmed against this machine's own real Dell SupportAssist install -- see rules.py):
the true push-event API, `UserNotificationListener.add_notification_changed()`, throws
`OSError: [WinError -2147023728] Element not found` for an unpackaged Python process on
this machine -- the same failure a public C#/WPF report describes for unpackaged apps,
resolved there only by packaging as a Windows Application Packaging Project. Rather than
require packaging this automation, this module polls `get_notifications_async()` on a
short interval instead -- confirmed live to detect a newly-posted toast within ~1s,
including its real `app_user_model_id` and heading text. This is polling, not a true OS
push callback, but it inspects the same notification-platform data a real listener
would see.

Also performs the deadline-fallback check: any local
reports/output/<run_id>_notification_state.json (see state.py) past its own
expected_fire_by and still "pending" is treated as a missed notification and resumed the
same way. This covers cases polling the notification itself cannot (e.g. the machine
fully off through the whole scheduled window, or the real notification never posting for
any other reason) -- see the notification-automation plan's "Known open risks" #6.

Usage:
    uv run python -m utils.notifications.listener
    uv run python -m utils.notifications.listener --poll-interval 10 --dry-run

Intended to be started once per logon via a Task Scheduler "At log on" trigger -- see
utils/notifications/scheduler.py. Runs until Ctrl+C (or Task Scheduler stops it).
"""

import argparse
import asyncio
import subprocess
import time

from winsdk.windows.ui.notifications import NotificationKinds
from winsdk.windows.ui.notifications.management import (
    UserNotificationListener,
    UserNotificationListenerAccessStatus,
)

from utils.notifications import state
from utils.notifications.rules import DEFAULT_RULES, NotificationRule, find_matching_rule


def P(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def _await(winrt_async_op):
    """winsdk's *_async() methods return an IAsyncOperation, not a native coroutine --
    asyncio.run() requires an actual coroutine object, so every call site needs this
    thin wrapper (confirmed live: calling asyncio.run() directly on the IAsyncOperation
    raises "ValueError: a coroutine was expected")."""
    return await winrt_async_op


def run_winrt(winrt_async_op):
    return asyncio.run(_await(winrt_async_op))


def ensure_access(listener) -> None:
    status = run_winrt(listener.request_access_async())
    if status != UserNotificationListenerAccessStatus.ALLOWED:
        raise SystemExit(
            f"Notification access not granted (status={status}) -- approve the Windows "
            "'Let this app access your notifications' prompt (Settings > Privacy > "
            "Notifications) and re-run."
        )


def _extract_heading(notification) -> str:
    """Returns the first text element of the notification's first visual binding --
    confirmed live this session this is the toast's own heading (e.g. "Check your PC
    Setup" for a real notification seen on this machine). Returns "" if the visual
    content isn't in the expected shape rather than raising -- a malformed/unusual
    notification shouldn't crash the whole polling loop over one bad item.
    """
    try:
        bindings = notification.notification.visual.bindings
        if not bindings:
            return ""
        text_elements = bindings[0].get_text_elements()
        return text_elements[0].text if text_elements else ""
    except Exception:
        return ""


def snapshot_ids(listener) -> set:
    notifications = run_winrt(listener.get_notifications_async(NotificationKinds.TOAST))
    return {n.id for n in notifications}


def poll_for_matching_rule(listener, rules: list, seen_ids: set) -> NotificationRule | None:
    """Returns the first matching rule for any NEW notification seen since the last
    poll, or None. Mutates seen_ids to include every notification id observed (matching
    or not), so each id is only ever evaluated once."""
    notifications = run_winrt(listener.get_notifications_async(NotificationKinds.TOAST))
    matched_rule = None
    for n in notifications:
        if n.id in seen_ids:
            continue
        seen_ids.add(n.id)
        aumid = n.app_info.app_user_model_id
        heading = _extract_heading(n)
        rule = find_matching_rule(rules, aumid, heading)
        if rule is not None:
            P(f"matching notification seen: id={n.id}, app_user_model_id={aumid!r}, heading={heading!r} -- rule={rule.name!r}")
            matched_rule = rule
    return matched_rule


def _claim_and_spawn(path, state_dict: dict, reason: str, dry_run: bool = False) -> None:
    """Claims ONE specific pending state file and spawns its own recorded scenario.
    Shared by both resume_all_pending() and check_deadline_fallback() -- neither calls
    subprocess.Popen()/mutates state directly, so there is exactly one place this
    happens."""
    run_id = state_dict.get("run_id")
    if not run_id:
        P(f"skipping malformed state file {path.name}: no run_id")
        return
    scenario = state_dict.get("scenario", state.DEFAULT_SCENARIO)
    command = [
        "uv", "run", "python", "-m", "orchestration.role_runner",
        "--role", "target", "--run-id", run_id,
        "--scenario", scenario,
    ]
    if dry_run:
        # Deliberately does NOT flip status to "resumed" -- a dry run must be
        # re-runnable/observable repeatedly without mutating state, unlike a real claim.
        # The real command runs RoleRunner.run() -> ensure_prerequisites(), which
        # (confirmed live) can attempt a real `winget install` of WinAppDriver with a
        # UAC prompt if it isn't already installed -- not something a test should
        # trigger as a side effect.
        P(f"[DRY RUN] would claim run_id={run_id} ({reason}) and spawn: {' '.join(command)}")
        return
    state.mark_resumed(path, state_dict, reason)
    P(f"claimed run_id={run_id} ({reason}) -- spawning {scenario}")
    subprocess.Popen(command, cwd=str(state.REPO_ROOT))


def resume_all_pending(reason: str, dry_run: bool = False) -> None:
    """Resumes EVERY currently-pending state file -- used by the real-notification-match
    path, where (per the documented "at most one pending reminder at a time" assumption)
    there's no way to map a notification match back to one specific run_id, so every
    pending file is treated as a candidate. NOT used by the deadline-fallback path --
    see check_deadline_fallback(), which only resumes files that are INDIVIDUALLY due
    (a real bug, found via live testing: resuming every pending file just because ANY
    ONE was due would incorrectly resume a second, genuinely-not-yet-due reminder too,
    if two were ever pending at once)."""
    for path in state.find_pending_state_files():
        state_dict = state.read_state(path)
        if state_dict is None:
            P(f"skipping unreadable state file {path.name}")
            continue
        if state_dict.get("status") != "pending":
            continue  # already claimed (by this path or the other one)
        _claim_and_spawn(path, state_dict, reason, dry_run=dry_run)


def check_deadline_fallback(dry_run: bool = False) -> bool:
    """Returns True if any pending reminder's deadline has passed. Resumes ONLY the
    file(s) that are individually due, not every pending file."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    any_due = False
    for path in state.find_pending_state_files():
        state_dict = state.read_state(path)
        if state_dict is None or state_dict.get("status") != "pending":
            continue
        try:
            expected_fire_by = datetime.fromisoformat(state_dict["expected_fire_by"])
        except (KeyError, ValueError):
            continue
        if now >= expected_fire_by:
            any_due = True
            _claim_and_spawn(path, state_dict, reason="deadline_fallback", dry_run=dry_run)
    return any_due


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--poll-interval", type=float, default=5.0)
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Log what would be claimed/spawned instead of actually doing it -- safe for "
             "testing, since the real spawn runs RoleRunner.run() -> "
             "ensure_prerequisites(), which can trigger a real WinAppDriver install.",
    )
    args = parser.parse_args()

    listener = UserNotificationListener.current
    ensure_access(listener)

    seen_ids = snapshot_ids(listener)
    rule_names = ", ".join(r.name for r in DEFAULT_RULES)
    P(
        f"notification_listener: watching for rules=[{rule_names}], "
        f"polling every {args.poll_interval}s ({len(seen_ids)} existing notification(s) ignored as baseline)"
        + (" [DRY RUN]" if args.dry_run else "")
    )

    while True:
        time.sleep(args.poll_interval)
        try:
            matched_rule = poll_for_matching_rule(listener, DEFAULT_RULES, seen_ids)
            if matched_rule is not None:
                resume_all_pending(reason=f"notification_matched:{matched_rule.name}", dry_run=args.dry_run)
        except OSError as exc:
            P(f"poll failed, will retry next cycle: {exc}")

        check_deadline_fallback(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
