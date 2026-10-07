"""
SourcePairingFlow: drives the Source PC from the Welcome screen through to a paired
state, continuously publishing the current pairing code to the Coordination Service so
the independent Target-side process can read and enter it.

Confirmed live (2026-10-06) via Phase 0 spike against the real Source build. Sequence:
Welcome screen -> click "Let's get started" -> trust-network dialog (accepted if shown)
-> "We're searching for your new PC." (discovery screen -- confirmed it does NOT advance
on its own; it waits for a real Target PC to become network-discoverable, confirmed by
waiting 15s+ with no change) -> pairing-code screen ("Let's finish linking your PCs.").

Confirmed live (2026-10-07): the trust-network dialog ("Do you trust the <network>
network?") is NOT reliably confined to the point right after "Let's get started" --
a user-supplied screenshot caught it layered over the pairing-code screen itself, well
into the publish loop. Same "can appear unpredictably, race it continuously" lesson
already learned for Target's ConfirmAccountsDialog/CloseAppsDialog. Both the
discovery-wait loop and _publish_loop() now check/accept it on every iteration, not just
once up front -- a one-shot check right after "Let's get started" is not enough.

The pairing code rotates every ~59s (confirmed directly by the user, 2026-10-06).
run() keeps re-reading and re-publishing the CURRENT code on a shorter
cadence than that rotation interval for as long as the pairing-code screen is showing,
so the Target side always has a valid, not-yet-expired code to enter. The loop ends when
the pairing-code screen stops showing (Target entered a correct code and pairing
advanced) or the overall timeout elapses.
"""

import time
from typing import Optional

from components.source.pairing_code_screen import PairingCodeScreen
from components.source.searching_screen import SearchingScreen
from components.source.trust_network_dialog import TrustNetworkDialog
from components.source.welcome_screen import WelcomeScreen
from factory.config import SOURCE_PROCESS_NAME
from factory.coordination_client import PAIRING_CODE_KEY, CoordinationClient
from factory.logger_factory import LoggerFactory
from factory.session import _find_main_window_hwnd

# Confirmed directly by the user (2026-10-06): the code regenerates every ~59s.
# Re-read/re-publish well inside that window so the Target side is never handed a code
# that's about to expire mid-entry.
CODE_REPUBLISH_INTERVAL_SECONDS = 5.0


class SourcePairingError(Exception):
    pass


class SourcePairingFlow:
    def __init__(self, app_session, run_id: str, coordination_client: Optional[CoordinationClient] = None):
        self.app_session = app_session
        self.run_id = run_id
        self.coordination_client = coordination_client or CoordinationClient()
        self.log = LoggerFactory.get_logger("source")

        self.welcome_screen = WelcomeScreen(app_session)
        self.trust_network_dialog = TrustNetworkDialog(app_session)
        self.searching_screen = SearchingScreen(app_session)
        self.pairing_code_screen = PairingCodeScreen(app_session)

    def _assert_app_alive(self) -> None:
        """Confirmed live (2026-10-06): the Source app can crash mid-wait (same
        WebView2 renderer-crash risk already documented for Target, see
        PROJECT_PLAN.md Sec 5.3b -- now confirmed to also affect Source). Without this
        check, a crashed window looks identical to "screen not showing yet" to every
        is_showing() call, so the flow silently polls a dead window until its outer
        timeout with a confusing, unhelpful error. Call this every iteration of any
        polling loop so a crash fails fast and clearly instead."""
        if _find_main_window_hwnd(SOURCE_PROCESS_NAME) is None:
            raise SourcePairingError(
                f"The Source app window is gone (process {SOURCE_PROCESS_NAME!r} not "
                "found) -- it most likely crashed mid-run, not a normal screen "
                "transition."
            )

    def run(self, discovery_timeout: float = 600.0, pairing_timeout: float = 600.0) -> None:
        """Drives through to the pairing-code screen, then keeps publishing the current
        code until pairing completes (screen advances) or pairing_timeout elapses.
        discovery_timeout bounds the "We're searching for your new PC." wait -- matches
        the app's own confirmed PairingTimeoutInMilliseconds (600000ms, 10 min; see
        PROJECT_PLAN.md) as a sane default, same reasoning as Target's
        wait_for_source_pc().
        """
        self.log.info("SourcePairingFlow starting")

        try:
            if self.welcome_screen.is_showing(timeout=5.0):
                self.log.info("Welcome screen showing -- clicking Let's get started")
                self.welcome_screen.click_get_started()
            else:
                self.log.info("Welcome screen not showing -- assuming already past it")

            if self.trust_network_dialog.accept(timeout=3.0):
                self.log.info("Trust-network dialog accepted")
            else:
                self.log.info("Trust-network dialog did not appear -- continuing")

            self.log.info(f"Waiting up to {discovery_timeout:.0f}s for the pairing-code screen...")
            deadline = time.monotonic() + discovery_timeout
            while time.monotonic() < deadline:
                self._assert_app_alive()
                if self.trust_network_dialog.accept(timeout=0.1):
                    self.log.info("Trust-network dialog accepted (appeared mid-discovery-wait)")
                if self.pairing_code_screen.is_showing(timeout=2.0):
                    break
                if not self.searching_screen.is_showing(timeout=1.0) and not self.pairing_code_screen.is_showing(timeout=1.0):
                    self.log.debug("Neither searching nor pairing-code screen showing yet -- still waiting")
                time.sleep(1.0)
            else:
                raise SourcePairingError(
                    f"Pairing-code screen never appeared within {discovery_timeout:.0f}s "
                    "-- no Target PC became discoverable in time"
                )

            self.log.success("Pairing-code screen showing -- entering publish loop")
            self._publish_loop(pairing_timeout)

        except BaseException as exc:
            # Same reasoning as SignInFlow.run(): BaseException, not Exception, so an
            # external interrupt (Ctrl+C, a killed background task) still logs clearly
            # here even though this flow doesn't own session teardown itself (that's the
            # caller's responsibility via Session.close(), same convention as
            # SignInFlow leaves to its own caller for non-internal failures).
            self.log.error(f"SourcePairingFlow failed: {type(exc).__name__}: {exc}")
            raise

        self.log.success("SourcePairingFlow complete -- pairing-code screen advanced (Target paired)")

    def _publish_loop(self, pairing_timeout: float) -> None:
        last_published = None
        deadline = time.monotonic() + pairing_timeout

        while time.monotonic() < deadline:
            self._assert_app_alive()
            if self.trust_network_dialog.accept(timeout=0.1):
                self.log.info("Trust-network dialog accepted (appeared mid-publish-loop)")
                continue
            if not self.pairing_code_screen.is_showing(timeout=1.0):
                self.log.success("Pairing-code screen no longer showing -- Target has paired")
                return

            try:
                code = self.pairing_code_screen.read_code()
            except RuntimeError as exc:
                # Confirmed live (2026-10-06): read_code() can genuinely fail on one
                # particular rotation (e.g. a harder-than-usual OCR misread, or more
                # boxes than usual missing from the UIA tree at once) while the very
                # next rotation reads cleanly -- this loop already re-reads and
                # re-publishes every CODE_REPUBLISH_INTERVAL_SECONDS regardless of
                # whether the code changed, specifically so a single bad read doesn't
                # need to be fatal. Log it and try again next cycle instead of ending
                # the whole flow over one unlucky rotation.
                self.log.warning(f"read_code() failed this cycle, will retry next cycle: {exc}")
                time.sleep(CODE_REPUBLISH_INTERVAL_SECONDS)
                continue

            if code != last_published:
                self.coordination_client.publish(self.run_id, PAIRING_CODE_KEY, code)
                self.log.success(f"Published pairing code to run_id={self.run_id!r}: {code}")
                last_published = code
            else:
                self.log.debug(f"Code unchanged ({code}) -- not re-publishing")

            time.sleep(CODE_REPUBLISH_INTERVAL_SECONDS)

        raise SourcePairingError(
            f"Pairing-code screen was still showing after {pairing_timeout:.0f}s -- "
            "Target never entered a correct code in time"
        )
