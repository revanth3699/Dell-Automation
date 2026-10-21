"""Where things live: CDM.db, the rclone/file-transfer log, the engine config, and the
per-run output directory. Every lookup is read-only and env-overridable."""

from __future__ import annotations

import os
import re
import shutil
from collections.abc import Mapping
from pathlib import Path

DEFAULT_CDM_DB = Path(r"C:\ProgramData\Dell\SupportAssist\CDM\CDM.db")
DEFAULT_LOG_DIRS = [Path(r"C:\ProgramData\Dell\SupportAssist\CDM\Logs"), Path(r"C:\ProgramData\Dell\SupportAssist\CDM")]
DEFAULT_CONFIG_CANDIDATES = [
    Path(r"C:\Program Files\Dell\SupportAssist\CDM\DellDataManager.exe.config"),
    Path(r"C:\Program Files (x86)\Dell\SupportAssist\CDM\DellDataManager.exe.config"),
]
DEFAULT_PROCESSES = ["MyDellExperience", "DellDataManager", "DellFileTransferUtil", "Everything"]
OUTPUT_ROOT = Path(__file__).resolve().parent / "output"


class CdmDbNotFound(FileNotFoundError):
    """CDM.db is not at the expected path (message names the path tried)."""


def _env(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _is_file(path: Path) -> bool:
    """is_file() that treats an access-denied / unreadable path as "not a usable file"
    rather than raising. Windows raises PermissionError from stat() on ACL-protected
    ProgramData\\Dell paths even just to test existence (seen live 2026-10-22)."""
    try:
        return path.is_file()
    except OSError:
        return False


def _is_dir(path: Path) -> bool:
    """is_dir() that treats an access-denied / unreadable path as "not a directory"."""
    try:
        return path.is_dir()
    except OSError:
        return False


def find_cdm_db(env: Mapping[str, str] | None = None) -> Path:
    override = _env(env).get("DDA_CDM_DB_PATH")
    path = Path(override) if override else DEFAULT_CDM_DB
    if not _is_file(path):
        source = "DDA_CDM_DB_PATH" if override else "the default location"
        raise CdmDbNotFound(
            f"CDM.db not found at {path} (taken from {source}); set DDA_CDM_DB_PATH to the real path"
        )
    return path


def find_rclone_log(env: Mapping[str, str] | None = None) -> Path | None:
    override = _env(env).get("DDA_RCLONE_LOG_PATH")
    if override:
        path = Path(override)
        return path if _is_file(path) else None
    candidates: list[Path] = []
    for directory in DEFAULT_LOG_DIRS:
        if _is_dir(directory):
            try:
                candidates += [p for p in directory.glob("*FileTransfer*.log*") if _is_file(p)]
            except OSError:
                continue
    def _mtime(p: Path) -> float:
        try:
            return p.stat().st_mtime
        except OSError:
            return 0.0
    return max(candidates, key=_mtime) if candidates else None


def find_engine_config(env: Mapping[str, str] | None = None) -> Path | None:
    override = _env(env).get("DDA_ENGINE_CONFIG_PATH")
    if override:
        path = Path(override)
        return path if _is_file(path) else None
    return next((p for p in DEFAULT_CONFIG_CANDIDATES if _is_file(p)), None)


def processes(env: Mapping[str, str] | None = None) -> list[str]:
    raw = _env(env).get("DDA_BENCHMARK_PROCESSES")
    if raw:
        names = [n.strip() for n in raw.split(",") if n.strip()]
        if names:
            return names
    return list(DEFAULT_PROCESSES)


def interval(env: Mapping[str, str] | None = None) -> float:
    try:
        value = float(_env(env).get("DDA_BENCHMARK_INTERVAL", "1.0"))
    except ValueError:
        return 1.0
    return value if value > 0 else 1.0


def _safe(run_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", run_id) or "run"


def output_dir(run_id: str, root: Path | None = None) -> Path:
    """benchmark/output/<run_id>/ -- created if missing."""
    path = (root or OUTPUT_ROOT) / _safe(run_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def prepare_output_dir(run_id: str, root: Path | None = None) -> Path:
    """Fresh output dir for a (possibly reused) run id: stale files are cleared first."""
    path = (root or OUTPUT_ROOT) / _safe(run_id)
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path
