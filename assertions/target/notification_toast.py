"""Existence check for the real Windows toast notification, via a desktop/Root
WinAppDriver session. PLACEHOLDER -- see locators/target/notification_toast.py; never
confirmed live. See the notification-automation plan's "Known open risks" #1.
"""

from assertions.common import text_exists

from locators.target.notification_toast import TOAST_LOCATOR


def is_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(session, TOAST_LOCATOR, "NotificationToast", timeout=timeout)
