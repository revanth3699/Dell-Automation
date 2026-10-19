"""Locators for components.target.notification_toast.NotificationToast.

PLACEHOLDER -- never confirmed live. Operates against a WinAppDriver session attached to
desktop_session_capabilities() (app: "Root"), not the Dell app's own window, since a
Windows toast is hosted by ShellExperienceHost/Action Center. Whether a Root session can
see this UI at all is unconfirmed -- see the notification-automation plan's "Known open
risks" #1 -- so this locator is a best guess at a generic toast shape, not a confirmed
match for the real Dell migration-reminder toast specifically.
"""

TOAST_LOCATOR = ("xpath", '//Window[@ClassName="ToastView"]')  # PLACEHOLDER, unconfirmed
