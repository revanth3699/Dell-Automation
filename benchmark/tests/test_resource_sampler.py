import json
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import psutil
import pytest

from benchmark import resource_sampler as rs

MB = 1024 * 1024
WALL = datetime(2026, 10, 22, 12, 0, 0)


class FakeProc:
    def __init__(self, pid, name, cpu=50.0, rss=100 * MB, read=0, write=0, handles=True, error=None):
        self.pid, self._name, self._cpu, self._rss = pid, name, cpu, rss
        self._read, self._write, self._handles, self._error = read, write, handles, error
        self.info = {"name": name}

    def _check(self):
        if self._error:
            raise self._error

    def name(self):
        self._check()
        return self._name

    def cpu_percent(self, interval=None):
        self._check()
        return self._cpu

    def memory_info(self):
        return SimpleNamespace(rss=self._rss)

    def io_counters(self):
        return SimpleNamespace(read_bytes=self._read, write_bytes=self._write)

    def num_threads(self):
        return 7

    def num_handles(self):
        if not self._handles:
            raise AttributeError("not windows")
        return 99


# ---- compute_rate
def test_compute_rate_normal():
    assert rs.compute_rate(0, 10 * MB, 2.0) == pytest.approx(5.0)


def test_compute_rate_zero_elapsed_guard():
    assert rs.compute_rate(0, MB, 0) == 0.0
    assert rs.compute_rate(0, MB, -1) == 0.0


def test_compute_rate_counter_reset_clamped():
    assert rs.compute_rate(10 * MB, 1 * MB, 1.0) == 0.0


def test_compute_rate_first_sample():
    assert rs.compute_rate(None, 10 * MB, 1.0) == 0.0


# ---- match_processes
def test_match_case_insensitive_and_exe():
    procs = [FakeProc(1, "dellfiletransferutil.EXE"), FakeProc(2, "notepad.exe"), FakeProc(3, "Everything")]
    got = rs.match_processes(procs, ["DellFileTransferUtil", "Everything"])
    assert [(n, p.pid) for n, p in got] == [("DellFileTransferUtil", 1), ("Everything", 3)]


def test_match_multiple_rclone_instances_and_dedupe():
    procs = [FakeProc(1, "DellFileTransferUtil.exe"), FakeProc(2, "DellFileTransferUtil.exe"),
             FakeProc(2, "DellFileTransferUtil.exe")]
    assert [p.pid for _, p in rs.match_processes(procs, ["DellFileTransferUtil"])] == [1, 2]


def test_match_empty_and_vanished():
    assert rs.match_processes([], ["x"]) == []
    gone = FakeProc(5, "DellDataManager", error=psutil.NoSuchProcess(5))
    gone.info = None
    assert rs.match_processes([gone], ["DellDataManager"]) == []


# ---- sample_process
def test_sample_process_maps_fields_and_rates():
    p = FakeProc(10, "DellFileTransferUtil", cpu=200.0, rss=300 * MB, read=0, write=40 * MB)
    rec, state = rs.sample_process("DellFileTransferUtil", p, None, 10.0, WALL, ncpu=4)
    assert rec["cpu_pct"] == 50.0 and rec["rss_mb"] == 300.0 and rec["pid"] == 10
    assert rec["disk_write_mbps"] == 0.0 and rec["handles"] == 99 and rec["threads"] == 7
    p._write = 140 * MB
    rec2, _ = rs.sample_process("DellFileTransferUtil", p, state, 12.0, WALL, ncpu=4)
    assert rec2["disk_write_mbps"] == pytest.approx(50.0)


def test_sample_process_no_handles_attr():
    rec, _ = rs.sample_process("x", FakeProc(1, "x", handles=False), None, 1.0, WALL)
    assert rec["handles"] is None


@pytest.mark.parametrize("err", [psutil.NoSuchProcess(1), psutil.AccessDenied(1)])
def test_sample_process_tolerates_vanished(err):
    assert rs.sample_process("x", FakeProc(1, "x", error=err), None, 1.0, WALL) == (None, None)


# ---- sample_system
def test_sample_system_rates():
    prev = {"mono": 0.0, "cpu_pct": 1, "mem_used_mb": 1, "disk_read": 0, "disk_write": 0, "net_sent": 0, "net_recv": 0}
    now = {"mono": 2.0, "cpu_pct": 33.333, "mem_used_mb": 4096.04, "disk_read": 20 * MB, "disk_write": 40 * MB,
           "net_sent": 4 * MB, "net_recv": 8 * MB}
    rec = rs.sample_system(prev, now, WALL)
    assert rec["scope"] == "system" and rec["cpu_pct"] == 33.33
    assert (rec["disk_read_mbps"], rec["disk_write_mbps"]) == (10.0, 20.0)
    assert (rec["net_sent_mbps"], rec["net_recv_mbps"]) == (2.0, 4.0)
    assert rs.sample_system(None, now, WALL)["net_recv_mbps"] == 0.0


def test_read_system_counters_with_fake_psutil():
    fake = SimpleNamespace(
        cpu_percent=lambda interval=None: 12.0,
        virtual_memory=lambda: SimpleNamespace(used=2 * MB),
        disk_io_counters=lambda: SimpleNamespace(read_bytes=1, write_bytes=2),
        net_io_counters=lambda: None)
    snap = rs.read_system_counters(5.0, fake)
    assert snap["mem_used_mb"] == 2.0 and snap["disk_write"] == 2 and snap["net_sent"] == 0


# ---- loop
def test_loop_meta_first_valid_json_and_stop_file(tmp_path):
    clock = {"t": 0.0}
    stop = tmp_path / "STOP"
    sleeps = []

    def sleep(s):
        sleeps.append(s)
        clock["t"] += 1.0
        if len(sleeps) == 3:
            stop.write_text("x")

    procs = [FakeProc(1, "DellFileTransferUtil.exe", write=0),
             FakeProc(2, "DellDataManager", error=psutil.AccessDenied(2))]
    procs[1].info = {"name": "DellDataManager"}
    counter = {"n": 0}

    def system_counters(mono):
        counter["n"] += 1
        return {"mono": mono, "cpu_pct": 5.0, "mem_used_mb": 1.0, "disk_read": 0, "disk_write": counter["n"] * MB,
                "net_sent": 0, "net_recv": 0}

    path = rs.run_sampler(tmp_path / "out", "target", "r1", 1.0, stop, ["DellFileTransferUtil", "DellDataManager"],
                          clock=lambda: clock["t"], sleep=sleep, now=lambda: WALL,
                          process_iter=lambda: procs, system_counters=system_counters, ncpu=2)
    lines = [json.loads(line) for line in Path(path).read_text().splitlines()]
    assert lines[0]["scope"] == "meta" and lines[0]["run_id"] == "r1" and lines[0]["cpu_count"] == 2
    scopes = [line["scope"] for line in lines[1:]]
    assert scopes.count("system") == 3 and scopes.count("process") == 3   # AccessDenied proc skipped
    assert lines[-1]["disk_write_mbps"] == pytest.approx(1.0)


def test_loop_duration_and_should_stop_and_bad_tick(tmp_path):
    clock = {"t": 0.0}

    def sleep(s):
        clock["t"] += 1.0

    def boom(mono):
        raise RuntimeError("counter failure")

    path = rs.run_sampler(tmp_path, "target", "r2", 1.0, None, ["x"], duration=2.5, clock=lambda: clock["t"],
                          sleep=sleep, now=lambda: WALL, process_iter=lambda: [], system_counters=boom, ncpu=1)
    assert len(Path(path).read_text().splitlines()) == 1          # meta only; ticks failed but did not crash
    path = rs.run_sampler(tmp_path, "source", "r3", 1.0, None, ["x"], should_stop=lambda: True,
                          process_iter=lambda: [], ncpu=1)
    assert len(Path(path).read_text().splitlines()) == 1


def test_main_runs_with_duration(tmp_path, monkeypatch):
    called = {}

    def fake_run(out, role, run_id, interval, stop_file, names, duration, **kw):
        called.update(out=out, role=role, names=names, duration=duration, stop=kw["should_stop"]())
        return out / "x.jsonl"

    monkeypatch.setattr(rs, "run_sampler", fake_run)
    assert rs.main(["--run-id", "r", "--out", str(tmp_path), "--duration", "1", "--processes", "a, b"]) == 0
    assert called["names"] == ["a", "b"] and called["duration"] == 1.0 and called["stop"] is False


def test_help_exits_zero(capsys):
    with pytest.raises(SystemExit) as e:
        rs.main(["--help"])
    assert e.value.code == 0
