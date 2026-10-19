"""Sends mock Windows toast notifications for testing utils/notifications/rules.py's
matching without needing the real Dell app to actually post one.

"For now", per explicit user direction (2026-10-19): since Dell hasn't delivered the
real GlassFloor/SupportAssist integration that would post a real migration-reminder
notification and relaunch the Target PC app from it (see
factory/session.py::_await_notification_then_attach(), kept for later use, not currently
called), orchestration/role_runner.py::TargetNotificationRunner wires
send_mock_toast_sequence() in as a stand-in trigger after Phase 1 sets the reminder.
utils/notifications/listener.py -- already running continuously as its own independent,
Task-Scheduler-managed process -- does the actual detection and launches the assigned
scenario on its own; nothing here waits for or drives that part.
"""

import time
from typing import Callable, Optional

from winsdk.windows.data.xml.dom import XmlDocument
from winsdk.windows.ui.notifications import ToastNotification, ToastNotificationManager

from utils.notifications.rules import DEFAULT_DELL_AUMID

# PLACEHOLDER headings, not confirmed production text -- see rules.py's own
# DEFAULT_RULES comment. "wrong" is deliberately chosen to NOT contain "Support Assist"
# (the configured rule's heading_contains), confirming real discrimination rather than
# just app-identity matching.
DEFAULT_WRONG_HEADING = "Unrelated notification (mock test)"
DEFAULT_RIGHT_HEADING = "Dell Support Assist: time to migrate (mock test)"
DEFAULT_INTERVAL_SECONDS = 10.0


def send_toast(aumid: str, heading: str, body: str) -> None:
    xml = XmlDocument()
    xml.load_xml(
        '<toast><visual><binding template="ToastGeneric">'
        f"<text>{heading}</text>"
        f"<text>{body}</text>"
        "</binding></visual></toast>"
    )
    toast = ToastNotification(xml)
    ToastNotificationManager.create_toast_notifier(aumid).show(toast)


def send_mock_toast_sequence(
    aumid: str = DEFAULT_DELL_AUMID,
    wrong_heading: str = DEFAULT_WRONG_HEADING,
    right_heading: str = DEFAULT_RIGHT_HEADING,
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
    log: Optional[Callable[[str], None]] = None,
) -> None:
    """Sends a wrong-heading toast (should be ignored by every configured rule), waits
    interval_seconds, then sends a right-heading toast (should match
    rules.DEFAULT_RULES and trigger the listener to resume whatever reminder is
    pending). Deliberately does NOT itself check whether the listener reacted -- that is
    the separately-running utils/notifications/listener.py process's job.
    """
    _log = log or print
    _log(f"Sending mock toast 1/2 (wrong heading, should be ignored): {wrong_heading!r}")
    send_toast(aumid, wrong_heading, "Mock toast for testing -- should NOT trigger anything")
    time.sleep(interval_seconds)
    _log(f"Sending mock toast 2/2 (right heading, should trigger): {right_heading!r}")
    send_toast(aumid, right_heading, "Mock toast for testing -- SHOULD trigger the assigned flow")
