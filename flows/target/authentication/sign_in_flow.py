"""
SignInFlow: automates the Target PC sign-in sequence end to end -- confirmed via live
testing and a user-supplied reference screenshot walkthrough, see
tools/phase0_inspection_notes.md and PROJECT_PLAN.md Sec 5.3.

Target-PC-only, confirmed directly by the user: Source PC has no authentication step at
all, so this flow (and all the components it depends on) lives entirely under the
target/ tree now, not shared/ -- there is no parameterize-by-role version of this flow
and there will not be one.

Sequence: click the app's sign-in button -> EITHER an external browser opens (fresh
sign-in needed: email page may or may not appear, depending on whether the browser
profile already has a session -> password page may or may not appear, same reason ->
email-OTP two-step verification -> Windows UAC, manual approval required, runs on the
secure desktop, invisible to automation) OR the app skips straight to a post-auth
transition screen with no browser at all (a valid session already existed under the
hood) -> either way: "Test, we're getting things ready" / "Starting the migration
assistant" transition screen(s) -> back in the app: "Connect to a trusted network" trust
dialog -> "We're looking for your other PC" (pairing-discovery screen -- the confirmed
end state of run() specifically; wait_for_source_pc() below is a separate, explicit
follow-up call for waiting past it. What specifically appears once Source is found --
the actual pairing-code exchange -- is pairing-flow work, not yet built).

Confirmed via a user-supplied flow diagram ("dell screens flow.pdf", 2026-10-05): the
post-OTP transition screen above is NOT a reliable success signal by itself -- it can
appear even when sign-in was cancelled or failed, in which case the app instead shows a
"There was a problem signing in" / "Sign-in failed. Please try again." dialog (with its
own Retry button) layered back over the Welcome screen. _run_fresh_auth_with_retry()
races these two outcomes and, on failure, clicks Retry and repeats the whole
browser-based email/password/OTP sequence from scratch, up to MAX_AUTH_RETRIES times.

Confirmed directly by the user (2026-10-06): this is not just a contingency for genuine
failures -- the OTP step's own negative-path check (below) deliberately drives this same
path on EVERY run's first attempt. Wrong OTP -> confirm the error banner -> click the
OTP page's own Cancel button (never the correct code in that same pass) -> this still
requires real UAC approval -> "There was a problem signing in" appears -> Retry -> a
second attempt submits correct values directly (no repeated negative checks) and
completes normally. There is no separate "cancel path" from "retry on failure" -- clicking
Cancel for the negative-path demo and recovering from a real failure both land on the
exact same Retry button and the exact same retry loop.

Four already-authenticated shortcuts are checked/handled before assuming a fresh
browser-based sign-in is needed -- confirmed via live testing that the app can have a
valid session even when the plain "Welcome to Dell" screen is showing (not just
"Welcome back"), and reveals this only after Sign In is clicked, by skipping the browser
entirely. See _already_signed_in() and _click_sign_in_with_retry() below.

This file is the orchestration layer only -- it holds no locators. All screen/dialog
elements live in components/target/ (Page Object layer), and browser-window attach lives
in factory/browser_driver_factory.py (Factory layer, also target-only in practice since
nothing else opens an external sign-in browser).

Known flakiness, confirmed via live testing: the first click/type on a WebView2 or
Chromium-hosted React element sometimes doesn't take effect even though the WinAppDriver
API call returns success (no error, just no visible effect) -- retrying is built into
each step below via a post-condition check + bounded retry loop, since a generic
"always double-click" approach could cause double-submits on steps where an extra click
has side effects.

Confirmed directly by the user (2026-10-06): email and password submit the correct value
directly every run -- NOT a wrong-then-right negative check. An earlier version ran that
check on every single routine run for all three steps, which (combined with OTP's own
deliberate wrong-value-then-cancel below, already happening every run by design)
accumulated enough incorrect password/OTP attempts across repeated runs to trip the
account's real 6-attempt lockout. OTP keeps its wrong-value-then-cancel specifically
because it's also how the cancel-and-retry mechanism gets exercised, not purely a
negative-path check. The full negative-path validation (all three steps, each wrong
value confirmed against its error banner, exact wording from "dell screens flow.pdf")
moved to tools/adhoc/ -- invoked deliberately when verifying error messages, never as
part of this default path.
"""

import time

from components.target.sign_in_screen import WelcomeScreen, WelcomeBackScreen
from components.target.common_dialogs import TrustNetworkDialog, MigrationPreparationTransition, SignInFailedDialog
from components.target.browser_sign_in_page import RestorePagesDialog, EmailStep, PasswordStep, OtpStep
from components.target.pairing_discovery_screen import PairingDiscoveryScreen
from factory.browser_driver_factory import browser_driver, list_browser_window_hwnds, find_new_browser_window_hwnd
from factory.driver_factory import DriverFactory
from factory.logger_factory import LoggerFactory
from factory.prerequisites import kill_winappdriver


class SignInError(Exception):
    pass


class SignInFlow:
    # Confirmed via a user-supplied flow diagram ("dell screens flow.pdf", 2026-10-05):
    # the post-OTP transition screen can appear even when sign-in was cancelled/failed,
    # and the app's own "There was a problem signing in" dialog has a Retry button that
    # restarts the browser-based sequence. This caps how many whole-flow restarts a
    # genuinely broken run gets before failing loudly instead of looping forever.
    MAX_AUTH_RETRIES = 3

    def __init__(self, app_session, username: str, password: str, otp: str):
        self.app_session = app_session
        self.username = username
        self.password = password
        self.otp = otp
        self.log = LoggerFactory.get_logger("target")
        # Set by _already_signed_in() when its "Welcome back" shortcut clicks Get
        # Started -- that's a real action (not a pure pass-through like the
        # pairing-discovery/trust-network shortcuts), so run() needs to know to wait for
        # UAC approval afterward too. See run()'s use of this flag.
        self._just_clicked_get_started = False

        self.welcome_screen = WelcomeScreen(app_session)
        self.welcome_back_screen = WelcomeBackScreen(app_session)
        self.trust_network_dialog = TrustNetworkDialog(app_session)
        self.migration_preparation_transition = MigrationPreparationTransition(app_session)
        self.sign_in_failed_dialog = SignInFailedDialog(app_session)
        self.pairing_discovery_screen = PairingDiscoveryScreen(app_session)

    def run(self, step_timeout: float = 20.0, overall_timeout: float = 300.0) -> None:
        # overall_timeout defaults much higher than the actual automated work needs --
        # confirmed via the user directly: after OTP succeeds, Windows shows a UAC
        # elevation prompt that a human must manually approve. UAC runs on the secure
        # desktop, which is categorically invisible to UI Automation/WinAppDriver -- there
        # is no API-level way to see or click it. This isn't a bug to fix; it's a hard
        # platform constraint. The flow just has to wait with real patience for a human
        # to notice and approve it.
        deadline = time.monotonic() + overall_timeout
        self.log.info("SignInFlow starting")

        try:
            if not self._already_signed_in():
                # Snapshot every browser window already open BEFORE clicking -- the OS
                # default browser is the user's everyday browser and is routinely already
                # running with unrelated windows open. Attaching to "the first window
                # found" (the original approach) silently grabbed the wrong window in
                # exactly that situation, see factory/browser_driver_factory.py.
                known_hwnds = list_browser_window_hwnds()
                opened_browser = self._click_sign_in_with_retry(known_hwnds)

                if opened_browser:
                    self._run_fresh_auth_with_retry(known_hwnds, step_timeout, deadline)
                else:
                    self.log.info(
                        "Sign-in click revealed an already-authenticated session (no "
                        "external browser opened) -- skipped credential entry. A "
                        "post-auth transition screen was detected, which (same as a "
                        "fresh sign-in) can still be gated behind manual UAC approval."
                    )
                    self._wait_for_uac_approval(remaining=deadline - time.monotonic())
            else:
                self.log.info(
                    "App already signed in (cached session detected before the sign-in "
                    "button) -- skipped credential entry, proceeding to confirm the "
                    "pairing-discovery end state."
                )
                # Bug fixed here, confirmed via a live run (2026-10-05): the
                # "Welcome back" shortcut's Get Started click can trigger the same
                # UAC-gated migration-prep transition a fresh sign-in does -- this
                # branch previously fell straight through to the trust-network wait
                # without ever waiting for that, so a real run timed out never reaching
                # the pairing-discovery screen. The OTHER two already-signed-in
                # shortcuts (pairing-discovery/trust-network dialog already showing)
                # are genuine pure pass-throughs with nothing to wait for -- only wait
                # here if Get Started was actually just clicked.
                if self._just_clicked_get_started:
                    self._wait_for_uac_approval(remaining=deadline - time.monotonic())

            self._wait_for_trust_network_and_accept(remaining=deadline - time.monotonic())
            self._confirm_reached_pairing_discovery(remaining=deadline - time.monotonic())
        except BaseException as exc:
            # BaseException, not Exception -- confirmed via live debris (2026-10-05): a
            # run interrupted externally (Ctrl+C, a background task killed) raises
            # KeyboardInterrupt, which does NOT inherit from Exception and was silently
            # skipping cleanup entirely, leaving orphaned browser windows/app
            # processes/WinAppDriver for the NEXT run to trip over (a stale leftover
            # Chrome sign-in window was mistaken for live progress in exactly this way).
            self.log.error(f"SignInFlow failed: {type(exc).__name__}: {exc}")
            self._cleanup_after_failure()
            raise

        self.log.success("SignInFlow complete -- reached pairing-discovery screen")

    def wait_for_source_pc(self, timeout: float = 600.0) -> bool:
        """Call this separately AFTER run() succeeds, if the pairing-discovery screen
        ("We're looking for your other PC") was reached -- not part of run() itself, so
        that method's confirmed end state (reaching this screen) stays unambiguous.

        Confirmed by the user (2026-10-05): this screen clears on its own once Source PC
        is found, regardless of whether Target reached it via a fresh sign-in or an
        already-logged-in shortcut. Returns whether it cleared within timeout. Default
        timeout matches the app's own confirmed PairingTimeoutInMilliseconds (600000ms,
        10 minutes) -- see PROJECT_PLAN.md.
        """
        if not self.pairing_discovery_screen.is_showing(timeout=2.0):
            self.log.info("wait_for_source_pc: pairing-discovery screen isn't showing -- nothing to wait for")
            return True
        self.log.info(f"Waiting up to {timeout:.0f}s for Source PC to be found...")
        found = self.pairing_discovery_screen.wait_until_source_found(timeout=timeout)
        if found:
            self.log.success("Source PC found -- pairing-discovery screen cleared")
        else:
            self.log.error(f"Source PC was not found within {timeout:.0f}s")
        return found

    def _cleanup_after_failure(self) -> None:
        # Confirmed requirement: if a single interaction fails anywhere in the flow, the
        # whole setup must be torn down rather than left half-finished for the next run
        # to trip over. The sign-in browser window (if one was attached) is already
        # closed by this point -- browser_driver()'s context manager (see run() and
        # factory/browser_driver_factory.py) closes + quits it on its way out via
        # exception unwind, before this method ever runs. The Target app and
        # WinAppDriver, by contrast, are safe to force-kill outright here: both are
        # entirely our own test infrastructure (see DriverFactory.kill_app() and
        # factory.prerequisites.kill_winappdriver()).
        try:
            DriverFactory.kill_app()
            self.log.info("Cleanup: killed the Target PC app process")
        except Exception as exc:
            self.log.error(f"Cleanup: failed to kill the Target PC app process: {exc}")

        try:
            if kill_winappdriver():
                self.log.info("Cleanup: stopped WinAppDriver")
            else:
                # Confirmed limitation: WinAppDriver normally runs elevated, and this
                # process isn't -- a non-elevated Stop-Process can't terminate a
                # higher-integrity one (same UIPI restriction noted elsewhere in this
                # codebase). Not silently claimed as success; logged honestly instead.
                self.log.error(
                    "Cleanup: WinAppDriver is still running -- likely still elevated "
                    "and this process isn't, so it couldn't be stopped automatically. "
                    "Stop it manually (or from an elevated prompt) if a clean restart "
                    "is needed."
                )
        except Exception as exc:
            self.log.error(f"Cleanup: failed to stop WinAppDriver: {exc}")

    def _already_signed_in(self) -> bool:
        # Confirmed via live log inspection (2026-10-05): the app can silently refresh a
        # cached OIDC refresh token (its own TrySilentLoginAsync, logged as
        # "hasAccessToken=True") on launch and skip the sign-in button entirely -- this
        # root-caused an earlier "click failed on 'SignInButton': Condition not met"
        # failure that looked like a crash/timing bug but wasn't one. Three distinct
        # already-signed-in screens have been observed; check for all of them before
        # assuming the sign-in button must be there.
        self.log.info("Checking for already-signed-in shortcuts before the Welcome screen")

        if self.pairing_discovery_screen.is_showing(timeout=3.0):
            self.log.success("Already signed in: pairing-discovery screen already showing")
            return True

        if self.trust_network_dialog.accept(timeout=1.0):
            self.log.success("Already signed in: trust-network dialog already showing -- accepted")
            return True

        # "Welcome back, <name>. Let's get you up and running." -- confirmed via a
        # user-supplied screenshot (2026-10-05). Unlike the two checks above, this is not
        # a no-op pass-through: the user confirmed directly that this screen's own blue
        # circular button must still be clicked to proceed.
        if self.welcome_back_screen.is_showing(timeout=1.0):
            self.log.info("Already signed in: 'Welcome back' screen showing -- clicking Get Started")
            self.welcome_back_screen.click_get_started()
            self._just_clicked_get_started = True
            return True

        self.log.info("No already-signed-in shortcut matched -- proceeding to the Welcome screen")
        return False

    def _click_sign_in_with_retry(self, known_hwnds, attempts: int = 3, wait_timeout: float = 45.0) -> bool:
        """Returns True if a new browser window opened (fresh browser-based sign-in
        needed); False if the app instead transitioned straight to a post-auth screen
        without ever opening a browser.

        Confirmed via live testing (2026-10-05): _already_signed_in()'s three checks
        don't catch every already-authenticated case -- the plain "Welcome to Dell"
        screen (not "Welcome back") can still show even when a valid session already
        exists underneath, and only clicking Sign In reveals that: instead of opening a
        browser, the app skips straight to the "Test, we're getting things ready"
        transition screen.

        Replaced an earlier short-fixed-window-then-reclick design (12s, then
        unconditionally click Sign In again regardless of state) -- confirmed via live
        testing that re-clicking after an arbitrary short timeout, rather than actually
        waiting for a recognized condition, caused a real failure: the app had already
        navigated away and the button no longer existed, so the "retry" click itself
        threw. This version instead waits patiently (up to wait_timeout) for one of
        several concrete conditions before ever giving up.

        Bug fixed here too, also confirmed via live testing: an intermediate version
        checked "is the Welcome screen gone?" on every quick poll cycle and treated that
        alone as "already authenticated, no browser" -- but the app's own "Sign in to
        MyDell to continue" waiting modal normally replaces the Welcome screen's content
        almost immediately after a REAL click too, well before the external browser
        necessarily has a visible top-level window yet. That made a perfectly normal,
        working browser-based sign-in look identical to the already-authenticated case
        and cut the wait short before the browser had a fair chance to appear. Checking
        "is the Welcome screen gone" is now only done AFTER the full wait_timeout has
        already elapsed with no other signal -- it decides whether to retry-click, not
        whether to give up on the browser early.
        """
        for attempt in range(attempts):
            self.log.info(f"Clicking Sign In on the Welcome screen (attempt {attempt + 1}/{attempts})")
            self.welcome_screen.click_sign_in()

            deadline = time.monotonic() + wait_timeout
            while time.monotonic() < deadline:
                if find_new_browser_window_hwnd(known_hwnds) is not None:
                    return True

                matched = self.migration_preparation_transition.wait_until_any_showing(timeout=0.1)
                if matched:
                    self.log.success(
                        f"User is already logged in -- transition screen detected: {matched!r}"
                    )
                    return False
                if self.trust_network_dialog.is_showing(timeout=0.1):
                    self.log.success("User is already logged in -- trust-network dialog detected")
                    return False
                if self.pairing_discovery_screen.is_showing(timeout=0.1):
                    self.log.success("User is already logged in -- pairing-discovery screen detected")
                    return False

                time.sleep(0.5)

            # Reached only after the FULL wait_timeout with no recognized outcome. Only
            # now check whether the Welcome screen is still there -- if it's gone, the
            # click plausibly worked but led somewhere none of the checks above
            # recognize yet; proceed without a browser rather than re-clicking a button
            # that isn't there. If it's still showing, the click plausibly had no effect
            # at all, which is worth an actual retry.
            if not self.welcome_screen.is_showing(timeout=1.0):
                self.log.info(
                    "Sign-in button no longer present after a full patient wait, with no "
                    "recognized post-auth screen either -- proceeding without a browser "
                    "rather than re-clicking a button that isn't there."
                )
                return False

            self.log.error(
                f"Sign-in click produced no recognized result after {wait_timeout:.0f}s "
                f"(attempt {attempt + 1}/{attempts}), Welcome screen still showing -- "
                f"retrying the click"
            )
        raise SignInError(
            "Sign-in button click neither opened the external browser nor showed a "
            "post-auth transition screen after all retries"
        )

    def _run_fresh_auth_with_retry(self, known_hwnds, step_timeout: float, deadline: float) -> None:
        """Runs the browser-based email/password/OTP sequence, then races the post-OTP
        outcome (_wait_for_auth_outcome): a recognized progress signal vs the "There was
        a problem signing in" dialog. Confirmed via a user-supplied flow diagram ("dell
        screens flow.pdf", 2026-10-05): that dialog's own screenshot is explicitly
        annotated "this will come even if Authentication is cancelled" -- meaning the
        transition screen is NOT a reliable success signal on its own; this race is what
        actually tells success and failure apart.

        On failure, clicks the dialog's own Retry button (not the Welcome screen's Sign
        In button -- the dialog is layered over that screen and has its own control) and
        repeats the whole browser-based sequence, up to MAX_AUTH_RETRIES times total,
        since the user confirmed a cancelled/failed sign-in must be retried from scratch,
        not patched up mid-flow.

        Confirmed directly by the user (2026-10-06): the OTP step's negative-path check
        (see _handle_otp_step) deliberately cancels instead of submitting the correct
        code on the FIRST attempt only -- so this loop's first iteration is EXPECTED to
        come back "failed" and retry, every run, by design. run_negative_check is only
        True on attempt 0; every subsequent attempt submits correct values directly.
        """
        for attempt in range(self.MAX_AUTH_RETRIES):
            run_negative_check = attempt == 0
            self.log.info("Attaching WinAppDriver session to the new sign-in browser window")
            # browser_driver() yields the session and guarantees it's closed + quit on
            # exit (success or exception) -- see factory/browser_driver_factory.py.
            with browser_driver(known_hwnds, timeout=step_timeout) as browser_session:
                self.log.success("Attached to the sign-in browser window")
                restore_pages_dialog = RestorePagesDialog(browser_session)
                restore_pages_dialog.dismiss_if_present()

                self._handle_email_step_if_present(browser_session, step_timeout)
                self._handle_password_step_if_present(browser_session, restore_pages_dialog, step_timeout)
                self._handle_otp_step(browser_session, restore_pages_dialog, step_timeout, run_negative_check)
            self.log.success("Closed the sign-in browser window after OTP submission")

            self.log.info(
                "OTP submitted (or deliberately cancelled). A Windows User Access "
                "Control (UAC) prompt may appear now -- automation cannot see or "
                "interact with it (it runs on the secure desktop). Please approve it "
                "manually if it appears; waiting..."
            )
            outcome = self._wait_for_auth_outcome(remaining=deadline - time.monotonic())

            if outcome == "success":
                return

            if outcome != "failed":
                raise SignInError(
                    "Neither a recognized success signal nor the sign-in-failed dialog "
                    "appeared within the time budget after OTP submission"
                )

            if run_negative_check:
                self.log.success(
                    "Negative-path check complete -- deliberately cancelled after the "
                    "wrong-OTP demo, as designed. Clicking Retry to continue with "
                    "correct values."
                )
            else:
                self.log.error(
                    f"Sign-in genuinely failed or was cancelled (attempt {attempt + 1}/"
                    f"{self.MAX_AUTH_RETRIES}) -- clicking Retry and restarting the "
                    "browser-based sequence"
                )
            known_hwnds = list_browser_window_hwnds()  # re-snapshot before Retry opens a new window
            if not self.sign_in_failed_dialog.retry():
                raise SignInError("Sign-in-failed dialog disappeared before Retry could be clicked")
            if not self._wait_for_new_browser(known_hwnds, timeout=30.0):
                raise SignInError("Clicking Retry on the sign-in-failed dialog never opened a new browser window")

        raise SignInError(f"Sign-in kept failing after {self.MAX_AUTH_RETRIES} whole-flow retries")

    def _wait_for_new_browser(self, known_hwnds, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if find_new_browser_window_hwnd(known_hwnds) is not None:
                return True
            time.sleep(0.5)
        return False

    def _wait_for_auth_outcome(self, remaining: float) -> str:
        """Races two outcomes after OTP submission -- see SignInFailedDialog's docstring
        for why this race, not just waiting for the transition screen alone, is what
        actually distinguishes success from failure/cancellation. Returns "success" or
        "failed"; "timeout" if the time budget runs out with neither appearing, which the
        caller treats as a hard error rather than silently assuming either outcome.
        """
        deadline = time.monotonic() + max(remaining, 5.0)
        while time.monotonic() < deadline:
            if self.sign_in_failed_dialog.is_showing(timeout=0.1):
                return "failed"
            matched = self.migration_preparation_transition.wait_until_any_showing(timeout=0.1)
            if matched:
                self.log.success(f"Sign-in succeeded -- transition screen detected: {matched!r}")
                return "success"
            time.sleep(0.5)
        return "timeout"

    def _handle_email_step_if_present(self, browser_session, timeout: float) -> None:
        # Bug fixed here, confirmed via live testing (2026-10-05): this used a hardcoded
        # 3.0s regardless of the caller's timeout, which ignored the parameter entirely.
        # 3.0s is not enough time for the real Dell OIDC page (an external network round
        # trip to www-poc.dell.com) to finish rendering right after a fresh browser
        # attach -- the check gave up before the field even existed yet, wrongly
        # concluded "already authenticated, skip", and left the real page sitting
        # untouched on the real email step while the flow moved on to check for
        # password/OTP elements that were never going to appear either.
        #
        # Confirmed directly by the user (2026-10-06): the wrong-value negative check
        # that used to run here on every attempt moved OUT of the default flow -- it
        # contributes to the SAME account as every other run today, and this step's
        # error banner has no lockout risk of its own, but running it unconditionally on
        # every single routine run was still unnecessary exposure. See tools/adhoc/ for
        # the dedicated negative-path error-message validation (all three steps,
        # deliberately invoked, not part of this default path).
        email_step = EmailStep(browser_session)
        if not email_step.is_showing(timeout=timeout):
            self.log.info("Email step: field not present -- browser profile already has a session, skipping")
            return
        self.log.info("Email step: field present")

        self.log.info("Email step: submitting the correct username")
        if not email_step.submit(self.username):
            raise SignInError("Email step did not advance after retries -- Continue click never took effect")
        self.log.success("Email step: advanced past the email page")

    def _handle_password_step_if_present(self, browser_session, restore_pages_dialog, timeout: float) -> None:
        # Same bug/fix as _handle_email_step_if_present above -- use the real timeout
        # budget, not a hardcoded 3.0s, since this page also needs a fresh navigation
        # (Email's Continue click) to render before this check can mean anything.
        #
        # Confirmed directly by the user (2026-10-06): the wrong-value negative check
        # moved OUT of this default path -- this step's own confirmed 6-attempt account
        # lockout warning is exactly why running it on every single routine run (on top
        # of OTP's own deliberate wrong-value-then-cancel below, which already happens
        # every run by design) was contributing to real account lockouts. See
        # tools/adhoc/ for the dedicated negative-path validation instead.
        restore_pages_dialog.dismiss_if_present()
        password_step = PasswordStep(browser_session)
        if not password_step.is_showing(timeout=timeout):
            self.log.info("Password step: field not present -- already authenticated in this browser profile, skipping")
            return
        self.log.info("Password step: field present")

        self.log.info("Password step: submitting the correct password")
        if not password_step.submit(self.password):
            raise SignInError("Password step did not advance after retries -- Sign In click never took effect")
        self.log.success("Password step: advanced past the password page")

    def _handle_otp_step(
        self, browser_session, restore_pages_dialog, timeout: float, run_negative_check: bool
    ) -> None:
        """On the negative-check pass (run_negative_check=True, the first whole-flow
        attempt): submits a deliberately wrong code, confirms the error banner, then
        clicks the OTP page's own Cancel button instead of ever submitting the correct
        code in this same pass -- confirmed directly by the user (2026-10-06). This
        deliberately drives _run_fresh_auth_with_retry()'s outcome race to "failed" and
        back through the Retry button, which is the SAME recovery path a genuine
        failure takes -- there is no separate "cancel path", by design.

        On a retry pass (run_negative_check=False), submits the correct code directly --
        the negative check has already been proven once this run.
        """
        otp_step = OtpStep(browser_session)
        if not otp_step.is_showing(timeout=timeout):
            self.log.info("OTP step: boxes not present -- already past this step somehow, skipping")
            return
        self.log.info("OTP step: boxes present")

        # Confirmed via testing: the first OTP box click can fail with a plain 500 from
        # WinAppDriver immediately after the password->OTP page transition, consistently
        # (not just once) -- most likely the "Restore pages?" dialog reappearing at this
        # new page load, not just right after the initial browser attach where it was
        # already handled once. Dismiss it again here, and give the page a moment to
        # finish settling before the first interaction.
        restore_pages_dialog.dismiss_if_present()
        time.sleep(1.0)

        if run_negative_check:
            # Same 6-attempt account-lockout reasoning as email/password -- single
            # attempt only. Each digit is rotated by one (mod 10) so the wrong code is
            # always the same length and never accidentally equals the real one.
            wrong_otp = "".join(str((int(digit) + 1) % 10) for digit in self.otp)
            self.log.info("OTP step: submitting a deliberately wrong code to verify the error message")
            if otp_step.submit_and_expect_error(wrong_otp):
                self.log.success("OTP step: error banner matched after the wrong code")
            else:
                self.log.error("OTP step: expected error banner did not appear after the wrong code")

            self.log.info(
                "OTP step: deliberately cancelling instead of submitting the correct "
                "code -- the retry mechanism (the same path a genuine failure takes) "
                "will complete this with correct values on the next pass"
            )
            if not otp_step.cancel():
                raise SignInError("OTP Cancel button not found/clicked after the negative check")
            self.log.info("OTP step: clicked Cancel")
            return

        self.log.info("OTP step: submitting the correct code")
        otp_step.submit(self.otp)
        self.log.success("OTP step: code submitted")

    def _wait_for_uac_approval(self, remaining: float) -> None:
        # Not capped to a short timeout (same reasoning as _wait_for_trust_network_and_accept
        # below) -- this wait spans the manual UAC approval, so it needs the real remaining
        # budget. Polling for any of the known transition phrases gives a concrete signal
        # that the human has actually clicked Yes and something moved forward, instead of
        # silently waiting with no visibility -- if nothing ever appears, something is
        # stuck (UAC dismissed/denied, or the app crashed) rather than just "still waiting
        # on a human."
        matched = self.migration_preparation_transition.wait_until_any_showing(timeout=max(remaining, 5.0))
        if matched:
            self.log.success(f"UAC approved -- transition screen detected: {matched!r}")

    def _wait_for_trust_network_and_accept(self, remaining: float) -> None:
        # Not capped to a short timeout here (unlike most other waits in this flow) --
        # this wait spans the manual UAC approval window, so it needs to use the real
        # remaining budget, not an arbitrarily short slice of it.
        self.log.info("Waiting for the 'Connect to a trusted network' dialog")
        if self.trust_network_dialog.accept(timeout=max(remaining, 5.0)):
            self.log.success("Trust-network dialog accepted")
        else:
            self.log.info("Trust-network dialog never appeared -- continuing without it")

    def _confirm_reached_pairing_discovery(self, remaining: float) -> None:
        self.log.info("Confirming the pairing-discovery screen ('We're looking for your other PC')")
        if not self.pairing_discovery_screen.wait_until_showing(timeout=remaining):
            raise SignInError(
                "Did not reach the pairing-discovery screen ('We're looking for your other "
                "PC') after sign-in -- check for an unexpected error dialog"
            )
        self.log.success("Pairing-discovery screen confirmed")
