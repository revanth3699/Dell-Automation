"""Reads the LIVE Windows registry on this machine (via the stdlib winreg module)
and compares it against a settings_backup.RegistryValueExpectation -- the "did this
setting actually end up applied" half of the validation. Only ever reads; never
writes to the registry.
"""

import time
import winreg
from dataclasses import dataclass
from typing import Optional, Union

from validation.settings_backup import RegistryValueExpectation

# Per explicit user direction (2026-10-14): re-check a value a couple more times
# before trusting a mismatch, in case the read landed exactly mid-write (a genuine
# registry race, not a measurement error). Only applied WHEN a mismatch is already
# found -- re-reading every value in a category that can hold 100+ values would
# make validation far slower for no benefit on the (common) values that already
# match on the first read.
#
# Important limitation, confirmed live: this guards against a value changing
# WITHIN this short re-check window (a second or two), not against it changing
# between two separate, independent validate_migration.py runs minutes apart --
# confirmed directly: the same "Hidden" value read as a clean match in one full
# run and a mismatch in another run 16 seconds later, with nothing in between
# that touched the registry. Each run only ever sees "what's true right now" --
# no amount of re-checking inside one run can see what it was, or will be, at a
# different run's own moment in time.
_MISMATCH_CONFIRM_ATTEMPTS = 3
_MISMATCH_CONFIRM_INTERVAL_SECONDS = 0.3

_HIVE_CONSTANTS = {
    "HKEY_CURRENT_USER": winreg.HKEY_CURRENT_USER,
    "HKEY_LOCAL_MACHINE": winreg.HKEY_LOCAL_MACHINE,
    "HKEY_USERS": winreg.HKEY_USERS,
    "HKEY_CLASSES_ROOT": winreg.HKEY_CLASSES_ROOT,
    "HKEY_CURRENT_CONFIG": winreg.HKEY_CURRENT_CONFIG,
}

# Confirmed live (2026-10-14): some values inside an otherwise-meaningful backed-up
# key are volatile runtime/telemetry state, not a durable user preference -- they're
# EXPECTED to differ between two machines regardless of whether migration worked
# correctly, so comparing them is pure noise. Confirmed TaskbarStateLastRun
# specifically holds steady across a few seconds on one machine (so it's not
# constantly ticking), but its name ("last run") and the fact it's a per-boot/
# per-logon counter means it will legitimately differ between the old PC's last
# session and the new PC's -- not a migration gap. The two WSENudge* values are
# excluded on the same reasoning (telemetry timestamps for a Windows "nudge"
# notification, confirmed present in the same Explorer\Advanced key dump). This list
# is deliberately small and name-based rather than a heuristic -- add to it only
# when a specific value is confirmed (not guessed) to be volatile/non-semantic.
_VOLATILE_VALUE_NAMES = {
    "TaskbarStateLastRun",
    "WSENudgeSentTimestamp",
    "WSENudgeDelayPeriodEvaluationTimestamp",
}


@dataclass
class RegistryCheckResult:
    expectation: RegistryValueExpectation
    found: bool
    live_data: Optional[Union[int, str, bytes, list]]
    matches: bool
    skipped_reason: Optional[str] = None
    # True only when a mismatch was found AND re-reading it a couple more times
    # (see _MISMATCH_CONFIRM_ATTEMPTS) disagreed between reads -- i.e. the live
    # value is actively changing right now, not just different from the backup.
    # False for every match, and for a mismatch that read the same way every time.
    unstable: bool = False


def read_live_value(hive: str, key_path: str, value_name: str):
    """Returns (found, data) for one registry value. found=False covers both "the
    key doesn't exist" and "the key exists but this value doesn't" -- both mean the
    same thing for validation purposes (expected data is simply not there)."""
    hive_const = _HIVE_CONSTANTS.get(hive)
    if hive_const is None:
        return False, None
    try:
        with winreg.OpenKey(hive_const, key_path) as key:
            data, _reg_type = winreg.QueryValueEx(key, value_name)
            return True, data
    except FileNotFoundError:
        return False, None
    except OSError:
        return False, None


def _normalize_for_comparison(value_type: str, data) -> Union[int, str, bytes, tuple, None]:
    """winreg hands back REG_MULTI_SZ as a list and REG_BINARY as bytes already --
    normalizes both sides of a comparison into hashable/comparable shapes (a list
    becomes a tuple) so int/str/bytes/tuple can all use plain ==.

    Bug fixed here, confirmed live (2026-10-14): a zero-length REG_BINARY value
    reads back from winreg.QueryValueEx() as None, not b'' -- confirmed directly
    (Telephony\\Locations\\KeyRenameHistory exists live, PowerShell shows it as an
    empty byte array, but winreg handed back None for it). The .reg-file side
    parses the same empty "hex:" value as b'' (see settings_backup.py's
    _decode_hex_bytes), so without this, an identical empty-on-both-sides value
    compared b'' == None -> False: a false mismatch, not a real migration gap.
    """
    if value_type == "binary" and data is None:
        return b""
    if isinstance(data, list):
        return tuple(data)
    return data


def _matches(expectation: RegistryValueExpectation, found: bool, live_data) -> bool:
    if not found:
        return False
    expected = _normalize_for_comparison(expectation.value_type, expectation.expected_data)
    actual = _normalize_for_comparison(expectation.value_type, live_data)
    return expected == actual


def check_value(expectation: RegistryValueExpectation) -> RegistryCheckResult:
    if expectation.value_name in _VOLATILE_VALUE_NAMES:
        return RegistryCheckResult(
            expectation=expectation, found=True, live_data=None, matches=True,
            skipped_reason="volatile runtime/telemetry value -- not meaningful to compare",
        )

    found, live_data = read_live_value(expectation.hive, expectation.key_path, expectation.value_name)
    if _matches(expectation, found, live_data):
        return RegistryCheckResult(expectation=expectation, found=found, live_data=live_data, matches=True)

    # First read shows a mismatch -- re-check a couple more times before trusting
    # it (see _MISMATCH_CONFIRM_ATTEMPTS's own docstring for exactly what this
    # does and doesn't protect against).
    readings = [(found, live_data)]
    for _ in range(_MISMATCH_CONFIRM_ATTEMPTS - 1):
        time.sleep(_MISMATCH_CONFIRM_INTERVAL_SECONDS)
        readings.append(read_live_value(expectation.hive, expectation.key_path, expectation.value_name))

    unstable = any(r != readings[0] for r in readings[1:])
    found, live_data = readings[-1]  # the most recent read is the final, authoritative one
    return RegistryCheckResult(
        expectation=expectation, found=found, live_data=live_data,
        matches=_matches(expectation, found, live_data), unstable=unstable,
    )
