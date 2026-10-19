"""Registry value comparison rules in validation/registry_live.py -- no registry access,
only _matches() with hand-built expectations."""

from pathlib import Path

from validation.registry_live import _matches
from validation.settings_backup import RegistryValueExpectation


def expectation(value_type, data):
    return RegistryValueExpectation(hive="HKEY_CURRENT_USER", key_path=r"Control Panel\International\User Profile",
                                    value_name="Languages", value_type=value_type, expected_data=data,
                                    source_file=Path("x.reg"))


def test_multi_sz_backed_up_as_escaped_string_matches_live_list():
    # confirmed live 2026-10-20: backup 'en-IN\0en-US' (literal backslash-zero) vs live list
    assert _matches(expectation("string", "en-IN\\0en-US"), True, ["en-IN", "en-US"])


def test_multi_sz_with_real_nul_separators_matches_live_list():
    assert _matches(expectation("string", "en-IN\x00en-US\x00"), True, ["en-IN", "en-US"])


def test_multi_sz_list_matches_list_regardless_of_trailing_empty():
    assert _matches(expectation("multi_string", ["a", "b"]), True, ["a", "b", ""])


def test_single_string_matches_one_element_live_list():
    assert _matches(expectation("string", "en-US"), True, ["en-US"])


def test_different_multi_sz_contents_do_not_match():
    assert not _matches(expectation("string", "en-IN\\0en-US"), True, ["en-US", "en-IN"])
    assert not _matches(expectation("string", "en-IN\\0en-US"), True, ["en-IN"])


def test_plain_values_unchanged():
    assert _matches(expectation("dword", 1), True, 1)
    assert not _matches(expectation("dword", 1), True, 2)
    assert not _matches(expectation("string", "a"), False, None)
    assert _matches(expectation("binary", b""), True, None)
