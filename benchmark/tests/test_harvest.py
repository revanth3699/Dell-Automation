import json
import sqlite3
from datetime import datetime, timedelta

import pytest

from benchmark import harvest, paths
from benchmark.models import Segment
from benchmark.tests import helpers as h
from benchmark.tests.helpers import T0


# ---- time parsing
def test_parse_ts_variants():
    assert harvest.parse_ts("2026-10-22 12:00:00.1234567") == datetime(2026, 10, 22, 12, 0, 0, 123456)
    assert harvest.parse_ts("2026-10-22T12:00:00") == T0
    assert harvest.parse_ts(T0) is T0
    assert harvest.parse_ts("2026-10-22T12:00:00Z").tzinfo is None
    assert harvest.parse_ts(None) is None and harvest.parse_ts("") is None and harvest.parse_ts("nope") is None


def test_parse_ts_assume_utc():
    # a string with an explicit Z is already handled the normal way -- assume_utc changes nothing
    normal = harvest.parse_ts("2026-10-22T12:00:00Z")
    assert harvest.parse_ts("2026-10-22T12:00:00Z", assume_utc=True) == normal
    # no marker at all: default behaviour treats it as already-local (no shift)...
    assert harvest.parse_ts("2026-10-22T12:00:00") == T0
    # ...assume_utc=True treats the SAME string as UTC needing conversion instead
    assert harvest.parse_ts("2026-10-22T12:00:00", assume_utc=True) == normal
    assert harvest.parse_ts(None, assume_utc=True) is None and harvest.parse_ts("", assume_utc=True) is None


def test_parse_runtime_and_eta():
    assert harvest.parse_runtime("01:02:03.5") == 3723
    assert harvest.parse_runtime("1.00:00:10") == 86410
    assert harvest.parse_runtime("garbage") is None and harvest.parse_runtime(None) is None
    assert harvest.parse_eta("6m36s") == 396
    assert harvest.parse_eta("1h2m3s") == 3723
    assert harvest.parse_eta("-") is None and harvest.parse_eta("") is None


# ---- read_episodes
def test_clean_migration_one_episode(tmp_path):
    eps = harvest.read_episodes(h.make_clean_db(tmp_path / "a.db"))
    assert len(eps) == 1
    ep = eps[0]
    assert ep.migration_id == 1 and ep.start == T0 and ep.end == T0 + timedelta(seconds=410)
    assert len(ep.segments) == 1 and ep.run_time == "00:06:50"
    assert (ep.migrated_from, ep.migrated_to, ep.network) == ("OLD-PC", "NEW-PC", "OFFICE-5G")
    names = {p.name: p for p in ep.phases}
    assert names["File transfer"].is_transfer and names["File transfer"].seconds == 300
    assert names["Settings migration"].seconds == 30
    assert "Unmeasured / other" in names and names["Unmeasured / other"].estimated
    # named "Migration info", not "Pre-check / migration info" -- it only ever matched
    # MigrationInfo* statuses, never PreCheck*/Pairing* ones (confirmed live 2026-10-22)
    assert "Migration info" in names and "Pre-check / migration info" not in names


def test_retry_same_id_two_segments(tmp_path):
    eps = harvest.read_episodes(h.make_retry_db(tmp_path / "b.db"))
    assert len(eps) == 1
    segs = eps[0].segments
    assert len(segs) == 2
    assert segs[0] == Segment(T0, T0 + timedelta(seconds=500))
    assert segs[1] == Segment(T0 + timedelta(seconds=500), T0 + timedelta(seconds=620))
    windows = harvest.expand_segments(eps)
    assert [(w.index, w.kind) for w in windows] == [(1, "primary"), (2, "retry")]
    assert windows[1].label == "Episode 2 - In-app Retry"
    retry_transfer = next(p for p in windows[1].phases if p.is_transfer)
    assert retry_transfer.seconds == 90


def test_try_again_two_ids(tmp_path):
    eps = harvest.read_episodes(h.make_try_again_db(tmp_path / "c.db"))
    assert [e.migration_id for e in eps] == [1, 2]
    assert eps[1].start == T0 + timedelta(seconds=1000)
    windows = harvest.expand_segments(eps)
    assert [w.kind for w in windows] == ["primary", "try_again"]


def test_three_episodes(tmp_path):
    windows = harvest.expand_segments(harvest.read_episodes(h.make_three_episode_db(tmp_path / "d.db")))
    assert [w.kind for w in windows] == ["primary", "retry", "try_again"]
    assert [w.index for w in windows] == [1, 2, 3]


def test_scope_to_run(tmp_path):
    # migration 1: start T0, end T0+620. migration 2: start T0+1000, end T0+1410.
    eps = harvest.read_episodes(h.make_three_episode_db(tmp_path / "d2.db"))
    far_end = T0 + timedelta(seconds=2000)
    assert harvest.scope_to_run(eps, None, None) == eps                      # no sampler meta -- no filtering
    assert harvest.scope_to_run(eps, T0, far_end) == eps                     # window covers everything
    # a run_start after migration 1 concluded but before migration 2 began should drop 1 (fully in
    # the past) and keep 2 (still ahead) -- end-based, not start-based (see scope_to_run's docstring).
    scoped = harvest.scope_to_run(eps, T0 + timedelta(seconds=700), far_end)
    assert [e.migration_id for e in scoped] == [2]
    # a migration that started long before this run but only concluded after it attached (the
    # real case the lower bound exists for) must still be kept.
    long_running = harvest.scope_to_run(eps, T0 + timedelta(seconds=615), far_end)
    assert [e.migration_id for e in long_running] == [1, 2]
    # upper bound: a migration that only starts AFTER this run's own window already ended must be
    # excluded even though its end is >= run_start -- otherwise re-harvesting an older run after a
    # later run's migration lands in CDM.db duplicates that migration into the older run's report
    # (confirmed live 2026-10-22: run 671 re-harvested after run 672 absorbed run 672's migration).
    before_mig2_starts = T0 + timedelta(seconds=900)
    bounded = harvest.scope_to_run(eps, T0, before_mig2_starts)
    assert [e.migration_id for e in bounded] == [1]


def test_status_without_audit_and_audit_without_status(tmp_path):
    conn = h.new_db(tmp_path / "e.db")
    conn.execute("INSERT INTO MigrationStatus (id, timeCreated, timeUpdated) VALUES (1, ?, ?)",
                 (h.iso_utc(T0), h.iso(T0 + timedelta(seconds=60))))
    conn.execute("INSERT INTO MigrationStatusAudit (migrationId, status, timeCreated) VALUES (9, 'MigrationStarted', ?)",
                 (h.iso_utc(T0 + timedelta(seconds=5)),))
    conn.execute("INSERT INTO MigrationStatus (id) VALUES (3)")      # no usable timestamps: dropped
    conn.commit()
    conn.close()
    eps = harvest.read_episodes(tmp_path / "e.db")
    assert [e.migration_id for e in eps] == [1, 9]
    assert eps[0].end == T0 + timedelta(seconds=60) and eps[1].start == T0 + timedelta(seconds=5)


def test_abandoned_stub_migration_is_dropped(tmp_path):
    """Confirmed live (2026-10-22): the real CDM.db creates a bare MigrationStatus row --
    migrationState 'Init', no audit trail, no start/end, timeUpdated left at .NET's
    DateTime.MinValue -- then abandons it and starts the real migration under a fresh id. Keeping
    it as an episode pushed the one real migration into the "Try Again" label by list position,
    even though nothing was ever retried."""
    conn = h.new_db(tmp_path / "f.db")
    conn.execute("INSERT INTO MigrationStatus (id, role, migrationState, timeCreated, timeUpdated)"
                 " VALUES (363, 'NewPC', 'Init', ?, '0001-01-01 00:00:00')", (h.iso_utc(T0),))
    h.add_migration(conn, 364, T0 + timedelta(seconds=1))   # the real migration, right after
    conn.commit()
    conn.close()
    eps = harvest.read_episodes(tmp_path / "f.db")
    assert [e.migration_id for e in eps] == [364]
    windows = harvest.expand_segments(eps)
    assert windows[0].kind == "primary"              # not "try_again" -- the stub no longer counts


def test_db_missing_and_locked_raise_typed_error(tmp_path):
    with pytest.raises(harvest.CdmDbError):
        harvest.read_episodes(tmp_path / "missing.db")
    path = h.make_clean_db(tmp_path / "locked.db")
    conn = sqlite3.connect(path, isolation_level=None, timeout=0.1)
    conn.execute("BEGIN EXCLUSIVE")
    try:
        sleeps = []
        with pytest.raises(harvest.CdmDbError):
            harvest._rows(path, "SELECT * FROM MigrationStatus", retries=2, delay=0, sleep=sleeps.append)
        assert len(sleeps) == 1
    finally:
        conn.execute("ROLLBACK")
        conn.close()


def test_missing_table_gives_empty(tmp_path):
    p = tmp_path / "empty.db"
    sqlite3.connect(p).close()
    assert harvest.read_episodes(p) == []
    assert harvest.read_drive_stats(p) == [] and harvest.read_file_counts(p) == {}


# ---- throughput
def test_parse_rclone_log_series():
    pts = harvest.parse_rclone_log(h.RCLONE_LOG.splitlines())
    assert len(pts) == 4                                  # malformed + marker-less lines skipped
    first, _second, third, last = pts
    assert (first.transferred, first.total, first.percent) == (100, 1000, 10.0)
    assert first.speed_bps == 52428800.5 and first.eta_s == 90 and (first.xfr_n, first.xfr_m) == (1, 10)
    assert first.ts == datetime(2026, 10, 22, 12, 1, 25) and first.errors == 0
    assert third.errors == 1 and third.eta_s is None
    assert last.xfr_n is None and last.eta_s == 3723 and last.ts == datetime(2026, 10, 22, 12, 7, 30)


def test_parse_rclone_log_without_timestamp_and_overflow():
    pts = harvest.parse_rclone_log(["INFO: 1 / 2, 50 %, 100, <|ETA|> 1s(xfr#1/2)"])
    assert pts[0].ts is None
    assert harvest.parse_rclone_log([]) == []


def test_read_throughput_no_log_and_with_log(tmp_path):
    assert harvest.read_throughput(None, None) == []
    assert harvest.read_throughput(None, tmp_path / "missing.log") == []
    log = tmp_path / "ft.log"
    log.write_text(h.RCLONE_LOG)
    db = h.make_three_episode_db(tmp_path / "t.db")
    pts = harvest.read_throughput(db, log)
    assert [p.kind for p in pts].count("rclone") == 4 and [p.kind for p in pts].count("drive") == 1


def test_read_throughput_combines_multiple_log_files(tmp_path):
    """log_path accepts several paths at once -- a run's real lines can be split across rotated
    files (confirmed live 2026-10-22), so every matching file must be read, not just one."""
    log_a, log_b = tmp_path / "a.log", tmp_path / "b.log.1"
    log_a.write_text(h.RCLONE_LOG)
    log_b.write_text(h.RCLONE_LOG)
    pts = harvest.read_throughput(None, [log_a, log_b])
    assert [p.kind for p in pts].count("rclone") == 8          # 4 valid points x 2 files
    assert harvest.read_throughput(None, [log_a, tmp_path / "missing.log"]) == \
           harvest.read_throughput(None, log_a)                 # a missing path in the list is just skipped


def test_drive_stats_latest_row_wins(tmp_path):
    drive = harvest.read_drive_stats(h.make_three_episode_db(tmp_path / "t.db"))[0]
    assert drive.drive == "C:\\" and drive.transferred == 1500000000 and drive.total == 2000000000
    assert (drive.already_existing, drive.files_copied, drive.files_failed, drive.files_existing) == (100000000, 90, 3, 4)


# ---- file counts
def test_file_counts_and_skip_buckets(tmp_path):
    counts = harvest.read_file_counts(h.make_three_episode_db(tmp_path / "t.db"))
    fc = counts[1]
    assert (fc.success, fc.backedup, fc.skipped, fc.already_existing) == (100, 2, 5, 7)
    assert fc.skip_reasons[0] == ("Permission denied", 2)
    assert dict(fc.skip_reasons) == {"Permission denied": 2, "File in use": 1, "Error code 99": 1, "Other": 1}
    counts_counts = [n for _, n in fc.skip_reasons]
    assert counts_counts == sorted(counts_counts, reverse=True)


def test_file_counts_empty_tables(tmp_path):
    conn = h.new_db(tmp_path / "z.db")
    conn.close()
    assert harvest.read_file_counts(tmp_path / "z.db") == {}


@pytest.mark.parametrize("reason,code,bucket", [
    ("Access is denied.", None, "Permission denied"), ("path too long here", 1, "Path too long"),
    ("Network connection lost", None, "Network / connection"), ("The volume for a file has been externally altered", None, "Drive removed"),
    ("not enough space on the disk", None, "Disk full"), ("", 7, "Error code 7"), (None, None, "Other"),
    ("who knows", 3, "Other")])
def test_bucket_skip_reason(reason, code, bucket):
    assert harvest.bucket_skip_reason(reason, code) == bucket


# ---- tuning
CONFIG = """<configuration><appSettings>
<add key="FileTransferUtilBandwidthLimit" value="50M"/>
<add key="FileTransferUtilParallelTransferCount" value="2"/>
<add key="Unrelated" value="1"/>
</appSettings></configuration>"""


def test_read_tuning_from_config(tmp_path):
    cfg = tmp_path / "e.config"
    cfg.write_text(CONFIG)
    t = harvest.read_tuning(cfg, cpu_count=12)
    rows = {r.flag: r for r in t.rows}
    assert not t.from_defaults and t.source == str(cfg)
    assert rows["--bwlimit"].value == "50M" and rows["--bwlimit"].note == ""
    assert rows["--transfers"].value == "8 (CPU count)" and "CPU count (12) capped at 8" in rows["--transfers"].note
    assert rows["--max-backlog"].value == "102400" and rows["--max-backlog"].note == "default"
    assert harvest.read_tuning(cfg, cpu_count=4).rows[0].value == "4 (CPU count)"


def test_read_tuning_missing_and_bad_config(tmp_path):
    t = harvest.read_tuning(None, cpu_count=2)
    assert t.from_defaults and "defaults" in t.source and t.rows[0].value == "2 (CPU count)"
    bad = tmp_path / "bad.config"
    bad.write_text("<not xml")
    t2 = harvest.read_tuning(bad)
    assert t2.from_defaults and "could not parse" in t2.source


# ---- samples
def test_read_samples(tmp_path):
    f = tmp_path / "r.jsonl"
    f.write_text("\n".join([
        json.dumps({"scope": "meta", "run_id": "x", "interval": 1.0}), "",
        json.dumps({"ts_wall": "2026-10-22T12:00:01.000", "ts_mono": 1.0, "scope": "system", "cpu_pct": 5}),
        "not json", json.dumps([1]), json.dumps({"ts_wall": "bad", "scope": "system"}),
        json.dumps({"ts_wall": "2026-10-22T12:00:02", "scope": "process", "name": "X", "pid": 1, "rss_mb": 2.0})]))
    meta, samples = harvest.read_samples(f)
    assert meta["run_id"] == "x" and len(samples) == 2 and samples[1].name == "X"
    assert harvest.read_samples(tmp_path / "none") == ({}, [])
    assert harvest.read_samples(None) == ({}, [])
    assert "ts_wall" in samples[0].to_dict() and "pid" not in samples[0].to_dict()


# ---- bucketing
def test_assign_samples_boundaries_and_dropped():
    ep1 = h.make_episode(T0, 100)
    ep2 = h.make_episode(T0 + timedelta(seconds=100), 100)
    s = [h.sys_sample(T0), h.sys_sample(T0 + timedelta(seconds=100)), h.sys_sample(T0 + timedelta(seconds=200)),
         h.sys_sample(T0 + timedelta(seconds=50)), h.sys_sample(T0 - timedelta(seconds=1)),
         h.sys_sample(T0 + timedelta(seconds=201))]
    dropped = harvest.assign_samples_to_episodes(s, [ep1, ep2])
    assert dropped == 2
    assert len(ep1.samples) == 3      # start, shared boundary (earlier window wins), midpoint
    assert len(ep2.samples) == 1


# ---- harvest_run
def test_harvest_run_full(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    lines = [json.dumps({"scope": "meta"})]
    for i in range(10):
        lines.append(json.dumps({"ts_wall": (T0 + timedelta(seconds=100 + i)).isoformat(), "ts_mono": i, "scope": "system"}))
    (out / "resources_target.jsonl").write_text("\n".join(lines))
    log = tmp_path / "ft.log"
    log.write_text(h.RCLONE_LOG)
    cfg = tmp_path / "e.config"
    cfg.write_text(CONFIG)
    r = harvest.harvest_run("r1", "target", out, {}, db_path=h.make_three_episode_db(tmp_path / "t.db"),
                            log_path=log, config_path=cfg)
    assert r.has_db and r.has_rclone_log and r.banners == []
    assert len(r.episodes) == 3 and len(r.samples) == 10
    assert len(r.episodes[0].samples) == 10 and r.episodes[0].file_counts.success == 100
    assert len(r.episodes[0].rclone) == 4 and r.episodes[1].file_counts.success == 100   # same id shares totals
    assert r.episodes[2].file_counts is None and r.episodes[2].drive_stats == []


def test_harvest_run_scopes_episodes_to_sampler_window(tmp_path):
    """CDM.db is persistent/cumulative across every migration ever run on the machine -- without
    scoping to the sampler's own [start_wall, last sample] window, an unrelated older migration
    (e.g. migration 1 here) would show up as an episode of this run too."""
    out = tmp_path / "out"
    out.mkdir()
    meta = {"scope": "meta", "start_wall": (T0 + timedelta(seconds=700)).isoformat()}
    last_sample = {"ts_wall": (T0 + timedelta(seconds=2000)).isoformat(), "ts_mono": 0, "scope": "system"}
    (out / "resources_target.jsonl").write_text(json.dumps(meta) + "\n" + json.dumps(last_sample))
    r = harvest.harvest_run("r3", "target", out, {}, db_path=h.make_three_episode_db(tmp_path / "t2.db"))
    assert [e.migration_id for e in r.episodes] == [2]


def test_harvest_run_combines_rotated_log_files(tmp_path, monkeypatch):
    """harvest_run's own log_path override, like paths.find_rclone_logs, must accept several
    files and combine them -- not just the one a caller happens to pass."""
    out = tmp_path / "out"
    out.mkdir()
    (out / "resources_target.jsonl").write_text(json.dumps({"scope": "meta"}))
    log_a, log_b = tmp_path / "a.log", tmp_path / "b.log.1"
    log_a.write_text(h.RCLONE_LOG)
    log_b.write_text(h.RCLONE_LOG)
    monkeypatch.setattr(paths, "DEFAULT_CONFIG_CANDIDATES", [])
    r = harvest.harvest_run("r4", "target", out, {}, db_path=h.make_three_episode_db(tmp_path / "t3.db"),
                            log_path=[log_a, log_b])
    assert r.has_rclone_log and [p.kind for p in r.rclone].count("rclone") == 8


def test_harvest_run_degrades_without_anything(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "DEFAULT_CDM_DB", tmp_path / "none.db")
    monkeypatch.setattr(paths, "DEFAULT_LOG_DIRS", [])
    monkeypatch.setattr(paths, "DEFAULT_CONFIG_CANDIDATES", [])
    r = harvest.harvest_run("r2", "target", tmp_path, {})
    assert not r.has_db and r.episodes == [] and not r.has_rclone_log
    text = " ".join(r.banners)
    assert "No resource samples" in text and "CDM.db unavailable" in text and str(tmp_path / "none.db") in text
    assert "No transfer log" in text and "Engine config not read" in text
