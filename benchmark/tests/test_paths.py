import os
import time

import pytest

from benchmark import paths


def test_cdm_db_default_shape_and_clear_failure(tmp_path, monkeypatch):
    assert str(paths.DEFAULT_CDM_DB).endswith(r"SupportAssist\CDM\CDM.db")
    with pytest.raises(paths.CdmDbNotFound) as e:
        paths.find_cdm_db({"DDA_CDM_DB_PATH": str(tmp_path / "nope.db")})
    assert str(tmp_path / "nope.db") in str(e.value) and "DDA_CDM_DB_PATH" in str(e.value)
    monkeypatch.setattr(paths, "DEFAULT_CDM_DB", tmp_path / "default.db")
    with pytest.raises(FileNotFoundError) as e2:
        paths.find_cdm_db({})
    assert str(tmp_path / "default.db") in str(e2.value)


def test_cdm_db_env_override_wins(tmp_path):
    db = tmp_path / "x.db"
    db.write_bytes(b"")
    assert paths.find_cdm_db({"DDA_CDM_DB_PATH": str(db)}) == db


def test_cdm_db_reads_os_environ_when_env_none(tmp_path, monkeypatch):
    db = tmp_path / "y.db"
    db.write_bytes(b"")
    monkeypatch.setenv("DDA_CDM_DB_PATH", str(db))
    assert paths.find_cdm_db() == db


def test_rclone_log_override_missing_and_search(tmp_path, monkeypatch):
    assert paths.find_rclone_log({"DDA_RCLONE_LOG_PATH": str(tmp_path / "none.log")}) is None
    log = tmp_path / "a.log"
    log.write_text("x")
    assert paths.find_rclone_log({"DDA_RCLONE_LOG_PATH": str(log)}) == log
    older, newer = tmp_path / "FileTransfer1.log", tmp_path / "FileTransfer2.log.1"
    older.write_text("o")
    newer.write_text("n")
    os.utime(older, (time.time() - 100, time.time() - 100))
    monkeypatch.setattr(paths, "DEFAULT_LOG_DIRS", [tmp_path / "missing", tmp_path])
    assert paths.find_rclone_log({}) == newer
    monkeypatch.setattr(paths, "DEFAULT_LOG_DIRS", [tmp_path / "missing"])
    assert paths.find_rclone_log({}) is None


def test_find_rclone_logs_returns_every_rotated_file(tmp_path, monkeypatch):
    """Confirmed live (2026-10-22): a run's real transfer-log lines can be split across rotated
    files (.log, .log.1, .log.2, ...) with the single newest holding none of them -- find_rclone_logs
    must return all of them, not just the one find_rclone_log would pick."""
    a, b, c = tmp_path / "FileTransfer1.log.2", tmp_path / "FileTransfer1.log.1", tmp_path / "FileTransfer1.log"
    for p, age in ((a, 200), (b, 100), (c, 0)):
        p.write_text(p.name)
        os.utime(p, (time.time() - age, time.time() - age))
    monkeypatch.setattr(paths, "DEFAULT_LOG_DIRS", [tmp_path])
    assert paths.find_rclone_logs({}) == [a, b, c]           # oldest first
    assert paths.find_rclone_logs({"DDA_RCLONE_LOG_PATH": str(b)}) == [b]   # override still pins one file
    assert paths.find_rclone_logs({"DDA_RCLONE_LOG_PATH": str(tmp_path / "none.log")}) == []
    monkeypatch.setattr(paths, "DEFAULT_LOG_DIRS", [tmp_path / "missing"])
    assert paths.find_rclone_logs({}) == []


def test_engine_config(tmp_path, monkeypatch):
    cfg = tmp_path / "e.config"
    cfg.write_text("<x/>")
    assert paths.find_engine_config({"DDA_ENGINE_CONFIG_PATH": str(cfg)}) == cfg
    assert paths.find_engine_config({"DDA_ENGINE_CONFIG_PATH": str(tmp_path / "no")}) is None
    monkeypatch.setattr(paths, "DEFAULT_CONFIG_CANDIDATES", [cfg])
    assert paths.find_engine_config({}) == cfg
    monkeypatch.setattr(paths, "DEFAULT_CONFIG_CANDIDATES", [])
    assert paths.find_engine_config({}) is None


def test_access_denied_paths_do_not_raise(tmp_path, monkeypatch):
    """Regression (found live 2026-10-22): on a PC with SupportAssist installed, the
    ACL-protected C:\\ProgramData\\Dell\\...\\Logs dir makes is_dir()/is_file() raise
    PermissionError. None of the lookups may propagate it."""
    from pathlib import Path

    def boom(self, *a, **k):
        raise PermissionError("[WinError 5] Access is denied")

    # is_dir / is_file on any path now raise, as Windows does for protected ProgramData dirs
    monkeypatch.setattr(Path, "is_dir", boom)
    monkeypatch.setattr(Path, "is_file", boom)

    monkeypatch.setattr(paths, "DEFAULT_LOG_DIRS", [tmp_path / "Logs"])
    monkeypatch.setattr(paths, "DEFAULT_CONFIG_CANDIDATES", [tmp_path / "x.config"])
    monkeypatch.setattr(paths, "DEFAULT_CDM_DB", tmp_path / "CDM.db")

    assert paths.find_rclone_log({}) is None          # no raise
    assert paths.find_rclone_logs({}) == []           # no raise
    assert paths.find_engine_config({}) is None        # no raise
    with pytest.raises(paths.CdmDbNotFound):           # treated as "not found", not a crash
        paths.find_cdm_db({})


def test_processes_and_interval():
    assert paths.processes({}) == paths.DEFAULT_PROCESSES
    assert paths.processes({"DDA_BENCHMARK_PROCESSES": "a, b ,"}) == ["a", "b"]
    assert paths.processes({"DDA_BENCHMARK_PROCESSES": " , "}) == paths.DEFAULT_PROCESSES
    assert paths.interval({}) == 1.0
    assert paths.interval({"DDA_BENCHMARK_INTERVAL": "0.5"}) == 0.5
    assert paths.interval({"DDA_BENCHMARK_INTERVAL": "abc"}) == 1.0
    assert paths.interval({"DDA_BENCHMARK_INTERVAL": "-2"}) == 1.0


def test_output_dir_creates_and_sanitises(tmp_path):
    d = paths.output_dir("run/../1", root=tmp_path)
    assert d.is_dir() and d.parent == tmp_path and "/" not in d.name
    assert paths.output_dir("", root=tmp_path).name == "run"


def test_prepare_output_dir_clears_stale(tmp_path):
    d = paths.output_dir("r", root=tmp_path)
    (d / "STOP_target").write_text("old")
    d2 = paths.prepare_output_dir("r", root=tmp_path)
    assert d2 == d and list(d2.iterdir()) == []
    assert paths.prepare_output_dir("fresh", root=tmp_path).is_dir()
