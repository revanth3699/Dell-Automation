"""The real Windows toast notification -- actions only, no existence checks. See
assertions/target/notification_toast.py's is_showing(). PLACEHOLDER, never confirmed
live -- see the notification-automation plan's "Known open risks" #1.
"""

from components.base_component import BaseComponent
from locators.target.notification_toast import TOAST_LOCATOR


class NotificationToast:
    def __init__(self, desktop_session):
        self._toast = BaseComponent(desktop_session, *TOAST_LOCATOR, "NotificationToast")

    def click(self) -> None:
        self._toast.click()
