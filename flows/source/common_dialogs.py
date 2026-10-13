"""Shared "race it continuously" checks used by BOTH SourcePairingFlow and
SourceTransferFlow -- extracted here (2026-10-14, per explicit user direction) since
each flow previously carried its own verbatim copy of these same two checks, which is
exactly how the "other PC disconnected" dialog's non-fatal-on-Source fix had to be
applied in two places by hand earlier today. Adding a new dialog that both flows need
to race now means editing this one file, not hunting through both.

Plain functions, not a shared base class: each flow already owns its own component
instances (constructed once in its own __init__, same as before) and just passes them
in here -- there's no new shared state or composed object to keep track of, only the
checking logic itself is shared. Mirrors components/target/common_dialogs.py's own
naming, which holds several dialogs shared across Target's flows the same way.
"""

from assertions.source import battery_critically_low_dialog as battery_critically_low_assertions
from assertions.source import confirm_cancel_dialog as confirm_cancel_assertions
from assertions.source import other_pc_network_disconnected_dialog as other_pc_network_disconnected_assertions


def check_other_pc_disconnected(app_session, dialog, log) -> bool:
    """"The other PC isn't connected to a network." -- means the Target PC lost its
    network connection. Confirmed directly by the user (2026-10-14): NOT fatal on
    Source (unlike Target's own mirror-image dialog, which IS confirmed terminal
    there) -- just click "Cancel transfer" and let the caller's loop continue."""
    if not other_pc_network_disconnected_assertions.is_showing(app_session, timeout=0.1):
        return False
    dialog.click_cancel_transfer()
    log.warning("The other PC isn't connected to a network. appeared -- clicked Cancel transfer")
    return True


def check_battery_critically_low(app_session, battery_dialog, confirm_cancel_dialog, log) -> bool:
    """"Your battery is critically low." -- dismissed via Cancel. Confirmed via
    user-supplied screenshots (2026-10-13): clicking Cancel triggers ConfirmCancelDialog
    ("Are you sure you want to cancel?"), asking to confirm cancelling the whole
    pairing/migration -- dismissed immediately too (via "No, don't cancel") so a
    follow-up confirmation never sits there until its own timeout."""
    if not battery_critically_low_assertions.is_showing(app_session, timeout=0.1):
        return False
    battery_dialog.click_cancel()
    log.warning("Your battery is critically low. appeared -- clicked Cancel")
    if confirm_cancel_assertions.is_showing(app_session, timeout=2.0):
        confirm_cancel_dialog.click_no_dont_cancel()
        log.warning(
            "Are you sure you want to cancel? appeared after dismissing the "
            "battery dialog -- clicked No, don't cancel"
        )
    return True
