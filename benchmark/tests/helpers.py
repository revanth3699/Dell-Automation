"""Shared test builders: a temp CDM.db with the real table schemas, rclone log text, and
Sample / Episode factories."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from benchmark.models import Episode, PhaseSpan, Sample, Segment, ThroughputPoint

T0 = datetime(2026, 10, 22, 12, 0, 0)

SCHEMA = """
CREATE TABLE MigrationStatus (id INTEGER PRIMARY KEY, role TEXT, migrationState TEXT, detailedStatus TEXT,
  sessionId TEXT, migratedFrom TEXT, runTime TEXT, timeCreated TEXT, timeUpdated TEXT,
  MigrationStartTime TEXT, MigrationEndTime TEXT, MigratedTo TEXT, Network TEXT);
CREATE TABLE MigrationStatusAudit (id INTEGER PRIMARY KEY AUTOINCREMENT, migrationId INTEGER, status TEXT, timeCreated TEXT);
CREATE TABLE MigrationFileCount (id INTEGER PRIMARY KEY AUTOINCREMENT, migrationId INTEGER, successFilesCount INTEGER,
  backedupFilesCount INTEGER, skippedFilesCount INTEGER, alreadyExistingFilesCount INTEGER);
CREATE TABLE RealTimeTransferStatistics (id INTEGER PRIMARY KEY AUTOINCREMENT, migrationId INTEGER, driveInfo TEXT,
  totalTransferSizePerDrive INTEGER, completedTransferSizePerDrive INTEGER, alreadyExistingSizePerDrive INTEGER,
  FilesCopiedPerDrive INTEGER, FailedFilesPerDrive INTEGER, AlreadyExistingFilesPerDrive INTEGER);
CREATE TABLE FileTransferResults (id INTEGER PRIMARY KEY AUTOINCREMENT, migrationId INTEGER, path TEXT, entity TEXT,
  parent INTEGER, isReplaced INTEGER, isSkipped INTEGER, replacedSize INTEGER, skippedSize INTEGER,
  skippingReason TEXT, errorCode INTEGER);
"""


def iso(dt: datetime, sep: str = " ") -> str:
    return dt.isoformat(sep=sep, timespec="microseconds") + "0"   # 7 fractional digits like .NET


def iso_utc(dt: datetime, sep: str = " ") -> str:
    """Like iso(), but stores dt's UTC-equivalent clock time with no timezone marker -- matching
    how the real CDM.db writes MigrationStatus.timeCreated / MigrationStatusAudit.timeCreated (see
    parse_ts's assume_utc docstring). dt.astimezone(timezone.utc) treats a naive dt as THIS
    machine's own local time, so parsing the result back with assume_utc=True reproduces dt
    exactly, regardless of which timezone the test machine runs in."""
    return iso(dt.astimezone(UTC).replace(tzinfo=None), sep)


def new_db(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn


# (offset seconds, status) of one clean migration, relative to its start
CLEAN_TRAIL = [(0, "CompatibilitySuccess"), (10, "MigrationInfoInit"), (20, "MigrationInfoDetailsSuccess"),
               (30, "SettingMigrationStarted"), (60, "SettingMigrationEnded"), (70, "MigrationStarted"),
               (80, "FileMigrationStarted"), (380, "FileCopyCompleted"), (390, "FileMigrationEnded"),
               (400, "MigrationReportRequest")]
RETRY_TRAIL = [(500, "MigrationStarted"), (510, "FileMigrationStarted"), (600, "FileCopyCompleted"),
               (610, "FileMigrationEnded")]


def add_migration(conn: sqlite3.Connection, mid: int, start: datetime, trail=CLEAN_TRAIL, end_offset: int = 410,
                  run_time: str = "00:06:50") -> None:
    conn.execute("INSERT INTO MigrationStatus (id, role, migrationState, migratedFrom, runTime, timeCreated, timeUpdated,"
                 " MigrationStartTime, MigrationEndTime, MigratedTo, Network) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                 (mid, "NewPC", "Completed", "OLD-PC", run_time, iso_utc(start), iso(start), iso(start),
                  iso(start + timedelta(seconds=end_offset)), "NEW-PC", "OFFICE-5G"))
    for off, status in trail:
        conn.execute("INSERT INTO MigrationStatusAudit (migrationId, status, timeCreated) VALUES (?,?,?)",
                     (mid, status, iso_utc(start + timedelta(seconds=off), "T")))


def make_clean_db(path: Path) -> Path:
    conn = new_db(path)
    add_migration(conn, 1, T0)
    conn.commit()
    conn.close()
    return path


def make_retry_db(path: Path) -> Path:
    conn = new_db(path)
    add_migration(conn, 1, T0, CLEAN_TRAIL + RETRY_TRAIL, end_offset=620)
    conn.commit()
    conn.close()
    return path


def make_try_again_db(path: Path) -> Path:
    conn = new_db(path)
    add_migration(conn, 1, T0)
    add_migration(conn, 2, T0 + timedelta(seconds=1000))
    conn.commit()
    conn.close()
    return path


def make_three_episode_db(path: Path) -> Path:
    conn = new_db(path)
    add_migration(conn, 1, T0, CLEAN_TRAIL + RETRY_TRAIL, end_offset=620)
    add_migration(conn, 2, T0 + timedelta(seconds=1000))
    conn.execute("INSERT INTO MigrationFileCount (migrationId, successFilesCount, backedupFilesCount, skippedFilesCount,"
                 " alreadyExistingFilesCount) VALUES (1, 100, 2, 5, 7)")
    conn.execute("INSERT INTO RealTimeTransferStatistics (migrationId, driveInfo, totalTransferSizePerDrive,"
                 " completedTransferSizePerDrive, alreadyExistingSizePerDrive, FilesCopiedPerDrive, FailedFilesPerDrive,"
                 " AlreadyExistingFilesPerDrive) VALUES (1, 'C:\\', 1000, 100, 0, 1, 0, 0)")
    conn.execute("INSERT INTO RealTimeTransferStatistics (migrationId, driveInfo, totalTransferSizePerDrive,"
                 " completedTransferSizePerDrive, alreadyExistingSizePerDrive, FilesCopiedPerDrive, FailedFilesPerDrive,"
                 " AlreadyExistingFilesPerDrive) VALUES (1, 'C:\\', 2000000000, 1500000000, 100000000, 90, 3, 4)")
    for reason, code in [("Access is denied", 5), ("Access is denied", 5), ("The process cannot access the file because it is being used", 32),
                         (None, 99), ("weird thing", None)]:
        conn.execute("INSERT INTO FileTransferResults (migrationId, path, entity, parent, isReplaced, isSkipped, replacedSize,"
                     " skippedSize, skippingReason, errorCode) VALUES (1, ?, 'File', 0, 0, 1, 0, 10, ?, ?)",
                     (f"p{conn.total_changes}", reason, code))
    conn.execute("INSERT INTO FileTransferResults (migrationId, path, entity, parent, isReplaced, isSkipped, replacedSize,"
                 " skippedSize, skippingReason, errorCode) VALUES (1, 'ok', 'File', 0, 0, 0, 0, 0, NULL, NULL)")
    conn.commit()
    conn.close()
    return path


RCLONE_LOG = """\
2026/10/22 12:01:25 INFO: 100 / 1000, 10 %, 52428800.5, <|ETA|> 1m30s(xfr#1/10)
2026/10/22 12:01:30 INFO: 200 / 1000, 20 %, 104857600, <|ETA|> 45s(xfr#2/10)
2026/10/22 12:01:31 ERROR : some/file.txt: Failed to copy: access denied
this line has no marker at all
2026/10/22 12:01:35 INFO: garbage / 1000, x %, speed, <|ETA|> nonsense
2026/10/22 12:01:40 INFO: 500 / 1000, 50 %, 31457280.0, <|ETA|> -(xfr#5/10)
2026-10-22 12:07:30 INFO: 900 / 1000, 90 %, 20971520, <|ETA|> 1h2m3s
"""


def sys_sample(t: datetime, cpu=10.0, disk_w=0.0, disk_r=0.0, net_r=0.0, net_s=0.0) -> Sample:
    return Sample(ts_wall=t, ts_mono=(t - T0).total_seconds(), scope="system", cpu_pct=cpu, mem_used_mb=4000.0,
                  disk_read_mbps=disk_r, disk_write_mbps=disk_w, net_recv_mbps=net_r, net_sent_mbps=net_s)


def proc_sample(t: datetime, name="DellFileTransferUtil", pid=100, cpu=30.0, rss=500.0, disk_w=50.0) -> Sample:
    return Sample(ts_wall=t, ts_mono=(t - T0).total_seconds(), scope="process", name=name, pid=pid, cpu_pct=cpu,
                  rss_mb=rss, disk_read_mbps=1.0, disk_write_mbps=disk_w, threads=10, handles=100)


def make_episode(start=T0, seconds=300, samples=None, transfer=True, bytes_moved=0) -> Episode:
    end = start + timedelta(seconds=seconds)
    ep = Episode(index=1, kind="primary", label="Episode 1 - Primary migration", migration_id=1, start=start, end=end,
                 segments=[Segment(start, end)], samples=list(samples or []))
    if transfer:
        ep.phases = [PhaseSpan("File transfer", start + timedelta(seconds=10), end - timedelta(seconds=10),
                               False, True)]
    if bytes_moved:
        ep.drive_stats = [ThroughputPoint(kind="drive", migration_id=1, drive="C:\\", transferred=bytes_moved,
                                          total=bytes_moved * 2)]
    return ep


def steady_samples(start=T0, n=20, **kw) -> list[Sample]:
    return [sys_sample(start + timedelta(seconds=15 + i), **kw) for i in range(n)]
