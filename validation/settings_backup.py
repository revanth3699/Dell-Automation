"""Loads the "ground truth" for Settings-copied validation: what Dell Migrate
actually backed up per setting category, from
C:\\ProgramData\\Dell\\SupportAssist\\CDM\\SettingsBackup\\<GUID>\\ -- confirmed live
(2026-10-14) to contain a Registry\\*.reg export (standard Windows Registry Editor
text format) per category, and occasionally a *.json sidecar (SPI.json for
wallpaper, Taskbar.json, folderOptions.json) for settings not expressed as a plain
registry dump.

The GUID folder names are opaque -- the category NAME (the same string the PDF
report's "Settings copied"/"Settings not migrated" lists use, e.g. "Taskbar
Settings") only appears in
C:\\ProgramData\\Dell\\SupportAssist\\CDM\\logs\\TargetPc\\DellDataAssistant-*.log,
which logs lines containing "SettingId: <guid>, SettingNameKey: <key>,
SettingNameValue: <name>," for every category considered. This module cross-references
the two to answer "which registry values were supposed to end up on this PC for
category X."

Confirmed live: SettingsBackup/ is ONE shared folder, overwritten in place by each
migration run (not kept per-run) -- it reflects only the MOST RECENT run, which is
exactly the one find_latest_report() in pdf_report_parser.py also picks.

Confirmed live: not every category has a non-empty Registry/ folder (e.g. "Microsoft
Edge Favorites" and "Fax Options" both had an empty Registry/ folder in a real run --
nothing to diff for those; callers must handle a category with zero expectations as
"nothing to verify", not a pass or a fail).
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Union

DEFAULT_CDM_ROOT = Path(r"C:\ProgramData\Dell\SupportAssist\CDM")

_SETTING_ID_RE = re.compile(
    r"SettingId:\s*([0-9a-zA-Z-]+),\s*SettingNameKey:\s*([^,]*),\s*SettingNameValue:\s*([^,]*),"
)

# .reg file grammar (Windows Registry Editor Version 5.00 export format):
#   [HKEY_X\key\path]                     -- section header, sets the current key
#   "ValueName"="a string"                -- REG_SZ
#   @="a string"                          -- REG_SZ, default value (empty name)
#   "ValueName"=dword:00000001            -- REG_DWORD
#   "ValueName"=hex:aa,bb,cc,...           -- REG_BINARY (can wrap across lines,
#                                              each continued line ending in "\")
#   "ValueName"=hex(2):...                -- REG_EXPAND_SZ (UTF-16LE bytes)
#   "ValueName"=hex(7):...                -- REG_MULTI_SZ (UTF-16LE bytes)
#   "ValueName"=hex(b):...                -- REG_QWORD (8 bytes, little-endian)
_SECTION_RE = re.compile(r'^\[(HKEY_[A-Z_]+)\\(.*)\]$')
_STRING_VALUE_RE = re.compile(r'^(@|"(?:[^"\\]|\\.)*")=(.*)$')


@dataclass
class RegistryValueExpectation:
    hive: str          # already resolved to HKEY_CURRENT_USER / HKEY_LOCAL_MACHINE -- see _resolve_hive()
    key_path: str       # e.g. "Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced"
    value_name: str     # "" means the key's default (@) value
    value_type: str      # "dword" | "string" | "binary" | "expand_string" | "multi_string" | "qword"
    expected_data: Union[int, str, bytes, List[str]]
    source_file: Path


@dataclass
class CategoryBackup:
    guid: str
    name: str
    registry_values: List[RegistryValueExpectation] = field(default_factory=list)
    other_backup_files: List[Path] = field(default_factory=list)  # *.json sidecars, not auto-compared yet


def _resolve_hive(raw_hive: str, raw_rest: str, current_user_sid: Optional[str]) -> Optional[tuple]:
    """Returns (resolved_hive, key_path) or None if this key can't be mapped to the
    CURRENTLY LOGGED IN user's registry (a backup made under a different user's SID
    than the one running this validation can't be checked here -- that's a real
    limitation, not a bug, so callers should surface it rather than silently skip).
    HKEY_LOCAL_MACHINE needs no translation.
    """
    if raw_hive == "HKEY_USERS":
        sid, _, rest = raw_rest.partition("\\")
        if current_user_sid is not None and sid == current_user_sid:
            return "HKEY_CURRENT_USER", rest
        return None
    return raw_hive, raw_rest


def _unescape_reg_string(raw: str) -> str:
    """Un-escapes a .reg-file string literal's \\" and \\\\ sequences (the two escapes
    .reg export actually uses)."""
    return raw.replace('\\"', '"').replace("\\\\", "\\")


def parse_reg_file(path: Path, current_user_sid: Optional[str]) -> List[RegistryValueExpectation]:
    # Confirmed live (2026-10-14): a real .reg export from this tool is plain UTF-8
    # text with NO byte-order mark at all (regedit's own exports are traditionally
    # UTF-16LE with a BOM, but this is not one of those) -- detect by BOM rather
    # than guessing UTF-16 first, which would silently mis-decode plain UTF-8 into
    # garbage (still non-empty, so a "retry if empty" fallback would never catch it).
    raw_bytes = path.read_bytes()
    if raw_bytes.startswith(b"\xff\xfe"):
        raw_text = raw_bytes.decode("utf-16-le", errors="ignore")
    elif raw_bytes.startswith(b"\xef\xbb\xbf"):
        raw_text = raw_bytes.decode("utf-8-sig", errors="ignore")
    else:
        raw_text = raw_bytes.decode("utf-8", errors="ignore")

    # Merge a hex value's wrapped continuation lines (each ends in "\") into one
    # logical line before splitting -- the standard .reg line-continuation rule.
    raw_text = re.sub(r"\\\s*\r?\n\s*", "", raw_text)

    expectations: List[RegistryValueExpectation] = []
    current_hive: Optional[str] = None
    current_key_path: str = ""

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(";") or line.startswith("Windows Registry Editor"):
            continue

        section_match = _SECTION_RE.match(line)
        if section_match:
            resolved = _resolve_hive(section_match.group(1), section_match.group(2), current_user_sid)
            if resolved is None:
                current_hive = None  # values under this header can't be checked -- skip them
            else:
                current_hive, current_key_path = resolved
            continue

        if current_hive is None:
            continue  # inside a section we couldn't resolve to this user

        value_match = _STRING_VALUE_RE.match(line)
        if not value_match:
            continue

        raw_name, raw_value = value_match.groups()
        value_name = "" if raw_name == "@" else _unescape_reg_string(raw_name[1:-1])

        if raw_value.startswith('"') and raw_value.endswith('"'):
            value_type, data = "string", _unescape_reg_string(raw_value[1:-1])
        elif raw_value.startswith("dword:"):
            value_type, data = "dword", int(raw_value[len("dword:"):], 16)
        elif raw_value.startswith("hex(2):"):
            value_type, data = "expand_string", _decode_hex_bytes(raw_value[len("hex(2):"):]).decode(
                "utf-16-le", errors="ignore"
            ).rstrip("\x00")
        elif raw_value.startswith("hex(7):"):
            raw_bytes = _decode_hex_bytes(raw_value[len("hex(7):"):])
            decoded = raw_bytes.decode("utf-16-le", errors="ignore")
            value_type, data = "multi_string", [s for s in decoded.split("\x00") if s]
        elif raw_value.startswith("hex(b):"):
            raw_bytes = _decode_hex_bytes(raw_value[len("hex(b):"):])
            value_type, data = "qword", int.from_bytes(raw_bytes, byteorder="little")
        elif raw_value.startswith("hex:") or re.match(r"^hex\(\d+\):", raw_value):
            # hex: (REG_BINARY) and any other hex(N): type not specifically handled
            # above are kept as raw bytes -- still comparable to winreg's own
            # REG_BINARY/unknown-type reads.
            prefix_len = raw_value.index(":") + 1
            value_type, data = "binary", _decode_hex_bytes(raw_value[prefix_len:])
        else:
            continue  # unrecognized value shape -- skip rather than guess

        expectations.append(
            RegistryValueExpectation(
                hive=current_hive, key_path=current_key_path, value_name=value_name,
                value_type=value_type, expected_data=data, source_file=path,
            )
        )

    return expectations


def _decode_hex_bytes(raw: str) -> bytes:
    byte_strs = [b for b in raw.split(",") if b.strip()]
    return bytes(int(b, 16) for b in byte_strs)


def build_guid_name_map(cdm_root: Path = DEFAULT_CDM_ROOT) -> Dict[str, str]:
    """Scans every TargetPc/DellDataAssistant-*.log for "SettingId: ..., ...,
    SettingNameValue: ...," entries and returns {guid: display_name}. The mapping is
    static per Dell Migrate build (the GUIDs are fixed identifiers for each setting
    category, not per-run), so scanning all available logs and keeping the first
    name seen per GUID is safe -- there is no expectation they'd ever disagree."""
    guid_to_name: Dict[str, str] = {}
    logs_dir = cdm_root / "logs" / "TargetPc"
    if not logs_dir.is_dir():
        return guid_to_name
    for log_path in logs_dir.glob("DellDataAssistant-*.log"):
        try:
            text = log_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for guid, _key, name in _SETTING_ID_RE.findall(text):
            guid_to_name.setdefault(guid, name)
    return guid_to_name


def load_category_backups(
    cdm_root: Path = DEFAULT_CDM_ROOT, current_user_sid: Optional[str] = None
) -> Dict[str, CategoryBackup]:
    """Returns {category_name: CategoryBackup} for every category folder currently
    under SettingsBackup/ (i.e. the most recent migration run). A category whose
    GUID isn't found in any log (shouldn't happen, but logs could theoretically be
    pruned) is keyed by its raw GUID instead of a name, so it's never silently
    dropped."""
    if current_user_sid is None:
        current_user_sid = get_current_user_sid()

    guid_to_name = build_guid_name_map(cdm_root)
    backups: Dict[str, CategoryBackup] = {}

    settings_backup_root = cdm_root / "SettingsBackup"
    if not settings_backup_root.is_dir():
        return backups

    for guid_folder in settings_backup_root.iterdir():
        if not guid_folder.is_dir():
            continue
        guid = guid_folder.name
        name = guid_to_name.get(guid, guid)

        registry_values: List[RegistryValueExpectation] = []
        registry_dir = guid_folder / "Registry"
        if registry_dir.is_dir():
            for reg_file in sorted(registry_dir.glob("*.reg")):
                registry_values.extend(parse_reg_file(reg_file, current_user_sid))

        other_files = [
            p for p in guid_folder.rglob("*")
            if p.is_file() and p.suffix.lower() not in (".reg",)
        ]

        backups[name] = CategoryBackup(
            guid=guid, name=name, registry_values=registry_values, other_backup_files=other_files,
        )

    return backups


def get_current_user_sid() -> Optional[str]:
    """Resolves the CURRENTLY LOGGED IN user's SID (via `whoami /user`, no extra
    dependency needed), so a backup's HKEY_USERS\\<old-pc-sid>\\... path can be
    matched to this user's own HKEY_CURRENT_USER. Confirmed live (2026-10-14): the
    migrated user keeps the SAME SID post-migration (the profile is carried over,
    not recreated), so this equality check is expected to hold -- if it doesn't,
    every registry expectation under HKEY_USERS silently becomes unresolvable (see
    _resolve_hive()), surfaced as "nothing to verify" rather than a crash, but
    callers validating a real run should notice an unexpectedly empty
    registry_values list and check this.
    """
    import subprocess

    try:
        result = subprocess.run(
            ["whoami", "/user", "/fo", "csv", "/nh"], capture_output=True, text=True, timeout=10,
        )
        # Output looks like: "DOMAIN\user","S-1-5-21-...-1001"
        parts = [p.strip('"') for p in result.stdout.strip().split('","')]
        if len(parts) == 2 and parts[1].startswith("S-1-"):
            return parts[1]
    except (OSError, subprocess.SubprocessError):
        pass
    return None
