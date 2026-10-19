"""Every Target overlay's REAL text (title + body from rebit's Resources.resx, as the
snapshot observer would see it) must be recognised as that overlay and no other.

Confirmed live (2026-10-20): the other-PC-offline body "Reconnect to a trusted network
to continue" contains the trust-network title "Connect to a trusted network" as a
substring, so the trust dialog's heading-only match claimed it and the run failed trying
to click a Trust network button that was not there. This test feeds each overlay's text
through the observer so any such collision fails here, not on the hardware."""

# ruff: noqa: ISC004  -- verbatim app copy, split across lines for readability
from __future__ import annotations

import pytest

from orchestration.statemachine import target_model
from orchestration.statemachine.observer import SnapshotObserver

# state id -> the strings the app renders for it (resx values, verbatim incl. curly quotes)
OVERLAY_TEXTS = {
    "trustNetwork": ["Connect to a trusted network",
                     "To protect your files and privacy, transfers should only take place on a trusted network. "
                     "Make sure you recognize and trust HomeWifi before continuing. Otherwise, select Cancel, "
                     "connect both PCs to a network you trust, and try again.", "Trust network", "Cancel"],
    "noNetwork": ["Connect this PC to a trusted network",
                  "To continue, connect this PC to a network you know and trust, like your home WiFi.", "Cancel transfer"],
    "otherPcNoNetwork": ["It looks like your network has been disconnected",
                         "Reconnect to a trusted network to continue. Once both PCs are online again, we'll "
                         "automatically reconnect and continue your transfer.", "Cancel transfer"],
    "batteryCritical": ["Plug into AC power",
                        "It looks like your battery is low. To avoid delays, plug your PC in to AC power and stay "
                        "plugged in during the transfer. We’ll close this window once you’re plugged in and ready "
                        "for the next step.", "Cancel transfer"],
    "accountMismatch": ["Your user account names don’t match",
                        "The names of the user accounts on your PCs aren’t the same. You can continue with these "
                        "accounts, or cancel the transfer and sign in again with matching accounts.",
                        "User account on this PC:", "User account on other PC:", "Cancel transfer", "Continue"],
    "closeApplications": ["Close other applications",
                          "Some applications are still running and could interrupt your transfer. Save any work "
                          "you’d like to keep, then close these applications to continue:", "Notepad",
                          "Cancel transfer", "Close applications"],
    "closeApplicationsFailed": ["Close all other applications",
                                "We could not close your applications. You need to retry manually. Click Retry once "
                                "you have closed the following applications:", "Check again", "Retry"],
    "installBrowser": ["Want to keep your browser bookmarks?",
                       "It looks like you have bookmarks on your old PC. To transfer them, install any browsers "
                       "with bookmarks you’d like to keep:", "Resume after installing, or Skip to continue without "
                       "transferring bookmarks.", "Skip", "Resume"],
    "noDeviceFound": ["Connect your other PC to HomeWifi",
                      "We’re still searching HomeWifi for your other PC. As soon as it’s connected, we’ll move on "
                      "to the next step.", "Cancel transfer"],
    "notAdmin": ["Admin access is required",
                 "You need to be signed in as an administrator to continue. Cancel the transfer and sign in as an "
                 "admin, then start again through SupportAssist. Learn more", "Cancel transfer"],
    "connectionLost": ["Connection lost", "We lost the connection to your other PC. Make sure both PCs are on the "
                       "same network, then try again.", "Cancel transfer", "Try again"],
    "migrationCancelled": ["The transfer was cancelled on your other PC",
                           "Try again now, or come back later and start a new transfer from Dell Data Assistant.",
                           "Try again"],
    "localeMismatch": ["Set both of your PCs to the same supported region",
                       "To continue, make sure your regional settings on both PCs are set to the same supported "
                       "region. Learn more", "Close"],
    "localeNotSupported": ["Set this PC’s location to a supported region",
                           "To continue, make sure your location is set to a supported region. You can find "
                           "instructions and a list of supported regions online.", "Close"],
    "failure": ["Something went wrong", "Something went wrong while getting your PCs ready (error 2468). Please "
                "close and try again.", "Close"],
    "signIn": ["Sign in to your Dell account",
               "We've opened your web browser so you can sign in and continue. We'll update this window when "
               "you're ready for the next step.", "Having trouble?", "Retry", "Cancel"],
    "signInLaunching": ["We’re getting your account ready", "This should only take a moment."],
    "signInFailed": ["We couldn’t sign you in", "The process may have been interrupted or taken too long to "
                     "complete.", "Retry to open a new window and try again.", "Cancel", "Retry"],
    "signOut": ["We’re signing you out of your Dell account", "This should only take a moment.", "Signing out..."],
    "signOutError": ["There was a problem signing out", "The process may have been interrupted or taken too long "
                     "to complete. Retry to open a new window and try again.", "Cancel", "Retry"],
    "feedbackModal": ["Tell us how we did", "We’d like to hear about your experience with Dell Migrate.",
                      "How would you rate your overall experience?", "What else would you like to share?",
                      "Tell us more", "Cancel", "Submit"],
    "driveMapping": ["We found multiple drives on your PCs", "Select the drives you want to transfer from and where "
                     "to save them on this PC.", "Your other PC", "This PC", "Rescan for connected drives",
                     "Cancel", "Apply"],
}

CLOSE_PROMPT_TEXTS = {
    "cancelMigrationConfirm": ["Are you sure you want to cancel?", "If you leave now, you’ll lose your current "
                               "progress, but you can always start a new transfer later.", "Yes, cancel", "No, continue"],
    "desktopShortcut": ["Add a desktop shortcut before you go", "You can always come back through SupportAssist, "
                        "but we can also add a shortcut that makes it easier to find later.", "No, thanks",
                        "Create shortcut"],
}


class FakeSession:
    def __init__(self, texts):
        self.page_source = "".join(f'<Text Name="{t}"/>' for t in texts)


@pytest.fixture(scope="module")
def observer():
    return SnapshotObserver(target_model.build(None))


@pytest.mark.parametrize("state_id", sorted(OVERLAY_TEXTS))
def test_overlay_text_is_recognised_as_that_overlay_only(observer, state_id):
    obs = observer.observe(FakeSession(OVERLAY_TEXTS[state_id]))
    assert obs.overlay == state_id, f"{state_id}'s own text was read as overlay={obs.overlay}"
    assert obs.close_prompt is None


@pytest.mark.parametrize("state_id", sorted(CLOSE_PROMPT_TEXTS))
def test_close_prompt_text_is_recognised(observer, state_id):
    obs = observer.observe(FakeSession(CLOSE_PROMPT_TEXTS[state_id]))
    assert obs.close_prompt == state_id


def test_overlay_over_a_screen_keeps_both(observer):
    texts = ["We’re transferring your files and settings"] + OVERLAY_TEXTS["otherPcNoNetwork"]
    obs = observer.observe(FakeSession(texts))
    assert (obs.screen, obs.overlay) == ("migrating", "otherPcNoNetwork")
