"""NotificationFlow: polls for the real Windows toast notification (via a desktop/Root
WinAppDriver session, not the Dell app's own window) and clicks it to reopen the app.

This is a passive watcher, not a scheduler -- the actual notification delay is owned
entirely by the Dell app/Windows' own notification-scheduling, independent of whether
this automation process is even running. See the notification-automation plan's Design
Sec 2 and "Known open risks" #1 -- whether a desktop/Root session can see a toast at all
is UNCONFIRMED in this environment (WinAppDriver isn't installed here).
"""

import time

from assertions.target import notification_toast as notification_toast_assertions
from components.target.notification_toast import NotificationToast
from factory.logger_factory import LoggerFactory


class NotificationFlowError(Exception):
    pass


class NotificationFlow:
    def __init__(self, desktop_session):
        self.desktop_session = desktop_session
        self.notification_toast = NotificationToast(desktop_session)
        self.log = LoggerFactory.get_logger("target")

    def wait_and_click(self, timeout: float, poll_interval: float = 2.0) -> None:
        self.log.info(f"Waiting up to {timeout}s for the migration-reminder notification...")
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if notification_toast_assertions.is_showing(self.desktop_session, timeout=poll_interval):
                self.notification_toast.click()
                self.log.success("Notification toast appeared -- clicked it")
                return
        raise NotificationFlowError(f"Notification toast never appeared within {timeout}s")
