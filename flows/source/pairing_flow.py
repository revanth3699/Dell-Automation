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

Per explicit user direction (2026-10-14): this file holds no existence-check locators.
Every is_X_showing() assertion is imported directly from assertions/source/<name>.py and
called with the raw app_session; components/source/ now holds only click/type/read
actions, called only after the matching assertion confirms presence.

Confirmed from a user-supplied screenshot (2026-10-14): "Your battery is critically
low." can also appear unpredictably during this flow -- same "race it continuously"
treatment as the trust-network/network-disconnected dialogs, raced in both the
discovery-wait loop and _publish_loop(). Dismissed via Cancel only after a delay
(BatteryCriticallyLowDialog.BATTERY_CRITICALLY_LOW_DELAY_SECONDS, per explicit user
direction, 2026-10-13), same reasoning as Target's PlugIntoAcPowerDialog.

Bug fixed here, confirmed via user-supplied screenshots (2026-10-13): clicking Cancel
on BatteryCriticallyLowDialog does NOT just dismiss it -- it triggers
ConfirmCancelDialog ("Are you sure you want to cancel?"), asking to confirm cancelling
the whole pairing/migration. Both call sites now go through the single
_check_battery_critically_low() helper, which dismisses that follow-up confirmation
too (via "No, don't cancel") immediately after every click_cancel() -- see
assertions/source/confirm_cancel_dialog.py's own docstring. This also folds the two
previously-separate inline battery-dialog checks (discovery-wait loop and
_publish_loop()) into one shared method, so this new handling only needed writing once.

Confirmed from a user-supplied screenshot (2026-10-14): "The other PC isn't connected
to a network." (the Target PC lost its network connection) can also appear
unpredictably during this flow -- raced in both loops the same way, via
_check_other_pc_disconnected(). Bug fixed here, confirmed directly by the user
(2026-10-14): this used to click "Cancel transfer" and then abort the whole run
(mirroring Target's own equivalent dialog, which IS confirmed terminal there) -- on
Source it isn't fatal, just clicked through and the loop keeps going.
"""

import time
from typing import Optional

import requests

from components.source.battery_critically_low_dialog import BatteryCriticallyLowDialog
from components.source.confirm_cancel_dialog import ConfirmCancelDialog
from components.source.network_disconnected_dialog import NetworkDisconnectedDialog
from components.source.other_pc_network_disconnected_dialog import OtherPcNetworkDisconnectedDialog
from components.source.pairing_code_screen import PairingCodeScreen
from components.source.trust_network_dialog import TrustNetworkDialog
from components.source.welcome_screen import WelcomeScreen
from assertions.source import (
    battery_critically_low_dialog as battery_critically_low_assertions,
    confirm_cancel_dialog as confirm_cancel_assertions,
    network_disconnected_dialog as network_disconnected_assertions,
    other_pc_network_disconnected_dialog as other_pc_network_disconnected_assertions,
    pairing_code_screen as pairing_code_assertions,
    searching_screen as searching_screen_assertions,
    trust_network_dialog as trust_network_assertions,
    welcome_screen as welcome_screen_assertions,
)
from factory.config import SOURCE_PROCESS_NAME
from utils.coordination_client import PAIRING_CODE_KEY, CoordinationClient
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
        self.network_disconnected_dialog = NetworkDisconnectedDialog(app_session)
        self.battery_critically_low_dialog = BatteryCriticallyLowDialog(app_session)
        self.confirm_cancel_dialog = ConfirmCancelDialog(app_session)
        self.other_pc_network_disconnected_dialog = OtherPcNetworkDisconnectedDialog(app_session)
        self.pairing_code_screen = PairingCodeScreen(app_session)

    def _check_other_pc_disconnected(self) -> bool:
        """Shared by every wait loop in this class, same reasoning as
        _check_battery_critically_low(). Confirmed directly by the user via a live
        screenshot (2026-10-14): "The other PC isn't connected to a network." means
        the Target PC lost its network connection.

        Bug fixed here, confirmed directly by the user (2026-10-14): this used to
        click "Cancel transfer" and then raise, aborting the whole run (mirroring
        Target's own OtherPcNetworkDisconnectedDialog, which IS confirmed terminal
        there) -- but on Source this isn't fatal. Just clicks "Cancel transfer" and
        lets the caller's loop continue, same "race it, click through, keep going"
        pattern as every other dialog in this class."""
        if not other_pc_network_disconnected_assertions.is_showing(self.app_session, timeout=0.1):
            return False
        self.other_pc_network_disconnected_dialog.click_cancel_transfer()
        self.log.warning("The other PC isn't connected to a network. appeared -- clicked Cancel transfer")
        return True

    def _check_battery_critically_low(self) -> bool:
        if not battery_critically_low_assertions.is_showing(self.app_session, timeout=0.1):
            return False
        self.battery_critically_low_dialog.click_cancel()
        self.log.warning('Your battery is critically low. appeared -- clicked Cancel')
        if confirm_cancel_assertions.is_showing(self.app_session, timeout=2.0):
            self.confirm_cancel_dialog.click_no_dont_cancel()
            self.log.warning(
                'Are you sure you want to cancel? appeared after dismissing the '
                "battery dialog -- clicked No, don't cancel"
            )
        return True

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
            if welcome_screen_assertions.is_showing(self.app_session, timeout=5.0):
                self.log.info("Welcome screen showing -- clicking Let's get started")
                self.welcome_screen.click_get_started()
            else:
                self.log.info("Welcome screen not showing -- assuming already past it")

            if trust_network_assertions.is_showing(self.app_session, timeout=3.0):
                self.trust_network_dialog.click_yes_continue()
                self.log.info("Trust-network dialog accepted")
            else:
                self.log.info("Trust-network dialog did not appear -- continuing")

            self.log.info(f"Waiting up to {discovery_timeout:.0f}s for the pairing-code screen...")
            deadline = time.monotonic() + discovery_timeout
            while time.monotonic() < deadline:
                self._assert_app_alive()
                if self._check_other_pc_disconnected():
                    continue
                if network_disconnected_assertions.is_showing(self.app_session, timeout=0.1):
                    self.network_disconnected_dialog.click_check_again()
                    self.log.warning(
                        "This PC isn't connected to a network appeared mid-discovery-wait "
                        "-- waited and clicked Check again"
                    )
                    continue
                if trust_network_assertions.is_showing(self.app_session, timeout=0.1):
                    self.trust_network_dialog.click_yes_continue()
                    self.log.info("Trust-network dialog accepted (appeared mid-discovery-wait)")
                if self._check_battery_critically_low():
                    continue
                if pairing_code_assertions.is_showing(self.app_session, timeout=2.0):
                    break
                if not searching_screen_assertions.is_showing(self.app_session, timeout=1.0) and not pairing_code_assertions.is_showing(self.app_session, timeout=1.0):
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
            if self._check_other_pc_disconnected():
                continue
            if network_disconnected_assertions.is_showing(self.app_session, timeout=0.1):
                self.network_disconnected_dialog.click_check_again()
                self.log.warning(
                    "This PC isn't connected to a network appeared mid-publish-loop "
                    "-- waited and clicked Check again"
                )
                continue
            if trust_network_assertions.is_showing(self.app_session, timeout=0.1):
                self.trust_network_dialog.click_yes_continue()
                self.log.info("Trust-network dialog accepted (appeared mid-publish-loop)")
                continue
            if self._check_battery_critically_low():
                continue
            if not pairing_code_assertions.is_showing(self.app_session, timeout=1.0):
                self.log.success("Pairing-code screen no longer showing -- Target has paired")
                return

            try:
                code = self.pairing_code_screen.read_code()
            except (RuntimeError, OSError, requests.exceptions.RequestException) as exc:
                # Confirmed live (2026-10-06): read_code() can genuinely fail on one
                # particular rotation (e.g. a harder-than-usual OCR misread, or more
                # boxes than usual missing from the UIA tree at once) while the very
                # next rotation reads cleanly -- this loop already re-reads and
                # re-publishes every CODE_REPUBLISH_INTERVAL_SECONDS regardless of
                # whether the code changed, specifically so a single bad read doesn't
                # need to be fatal. Log it and try again next cycle instead of ending
                # the whole flow over one unlucky rotation. Broadened beyond RuntimeError
                # to also cover a flaky WinAppDriver screenshot call or corrupt-PNG read
                # (OSError/PIL.UnidentifiedImageError) one layer down in read_code()'s
                # own OCR fallbacks -- same "retry next cycle" treatment, not fatal.
                self.log.warning(f"read_code() failed this cycle, will retry next cycle: {exc}")
                time.sleep(CODE_REPUBLISH_INTERVAL_SECONDS)
                continue

            if code != last_published:
                try:
                    self.coordination_client.publish(self.run_id, PAIRING_CODE_KEY, code)
                except requests.exceptions.RequestException as exc:
                    # A transient blip talking to the Coordination Service (connection
                    # reset, 5xx, service mid-restart) shouldn't be fatal either -- this
                    # loop already re-reads and re-publishes every
                    # CODE_REPUBLISH_INTERVAL_SECONDS, so the next cycle's publish just
                    # retries with whatever code is current then.
                    self.log.warning(f"Publishing pairing code failed this cycle, will retry next cycle: {exc}")
                else:
                    self.log.success(f"Published pairing code to run_id={self.run_id!r}: {code}")
                    last_published = code
            else:
                self.log.debug(f"Code unchanged ({code}) -- not re-publishing")

            time.sleep(CODE_REPUBLISH_INTERVAL_SECONDS)

        raise SourcePairingError(
            f"Pairing-code screen was still showing after {pairing_timeout:.0f}s -- "
            "Target never entered a correct code in time"
        )
