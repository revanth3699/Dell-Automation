import json
import re
from datetime import timedelta

import pytest

from benchmark import correlate, harvest, report
from benchmark.models import FileCounts, RunReport, ThroughputPoint, Tuning
from benchmark.tests import helpers as h
from benchmark.tests.helpers import T0, make_episode, proc_sample, steady_samples


def payload_of(html: str) -> dict:
    m = re.search(r"window\.__BENCHMARK__ = (\{.*?\});\n?</script>", html, re.S)
    assert m, "payload not found"
    return json.loads(m.group(1).replace("<\\/", "</"))


def run_with(n_episodes: int) -> RunReport:
    eps = []
    for i in range(n_episodes):
        ep = make_episode(start=T0 + timedelta(seconds=1000 * i), samples=[], bytes_moved=2 * 1024 ** 3)
        ep.index, ep.migration_id = i + 1, i + 1
        ep.label = f"Episode {i + 1} - Primary migration"
        ep.samples = [s for s in steady_samples(start=ep.start, cpu=30.0, disk_w=100.0, net_r=10.0)] + \
                     [proc_sample(ep.start + timedelta(seconds=20 + k)) for k in range(5)]
        ep.rclone = [ThroughputPoint(kind="rclone", ts=ep.start + timedelta(seconds=30 + 5 * k),
                                     speed_bps=(40 + k) * 1024 ** 2, eta_s=600 - k * 30) for k in range(10)]
        ep.file_counts = FileCounts(10, 1, 2, 3, [("Permission denied", 2)])
        eps.append(ep)
    all_samples = [s for e in eps for s in e.samples]
    r = RunReport("run-1", "target", T0, episodes=eps, samples=all_samples,
                  tuning=Tuning(rows=[], from_defaults=True, source="defaults"))
    return correlate.annotate(r, {})


@pytest.mark.parametrize("n", [0, 1, 3])
def test_render_episode_counts(tmp_path, n):
    out = report.render(run_with(n), tmp_path / "r.html")
    html = out.read_text(encoding="utf-8")
    p = payload_of(html)
    assert len(p["episodes"]) == n and p["rollup"]["id"] == 0
    assert 'id="episodes"' in html and 'class="tab"' in html
    assert report.PLACEHOLDER not in html and "SAMPLE DATA" not in html and "const T = Array.from" not in html
    assert "Chart.js/4.4.1/chart.umd.min.js" in html and "window.__BENCHMARK__" in html


def test_render_default_path_uses_output_dir(tmp_path, monkeypatch):
    from benchmark import paths
    monkeypatch.setattr(paths, "OUTPUT_ROOT", tmp_path)
    out = report.render(run_with(1))
    assert out == tmp_path / "run-1" / "report_target.html" and out.is_file()


def test_view_content_full_data(tmp_path):
    p = payload_of(report.render(run_with(1), tmp_path / "r.html").read_text(encoding="utf-8"))
    v = p["episodes"][0]
    assert len(v["labels"]) == len(v["thr"]["instant"]) == len(v["res"]["cpu"]["system"])
    assert any(x is not None for x in v["thr"]["instant"]) and any(x is not None for x in v["thr"]["eta"])
    assert [x["name"] for x in v["procs"]] == ["DellFileTransferUtil"]
    assert v["tiles"][1]["v"] == "2.0 GB" and v["tiles"][3]["v"] == "10"
    assert v["phases"][0][0] == "File transfer" and v["phases"][0][2] == "x"
    assert v["skips"]["labels"] == ["Permission denied"] and v["files"]["values"] == [10, 3, 2, 1]
    assert v["busy"] and v["verdict"]["text"] and all(val is None for val in v["empty"].values())
    assert "Episode 1" in p["sub"] or "Run run-1" in p["sub"]


def test_missing_planes_show_banners_and_messages(tmp_path):
    r = RunReport("run-2", "target", T0, banners=["CDM.db unavailable (x); showing a resource-only report."],
                  samples=steady_samples(n=5))
    p = payload_of(report.render(r, tmp_path / "r.html").read_text(encoding="utf-8"))
    assert p["banners"] and p["episodes"] == []
    roll = p["rollup"]
    assert "transfer log" in roll["empty"]["thr"] and "phase" in roll["empty"]["phase"].lower()
    assert roll["empty"]["drive"] and roll["empty"]["files"] and roll["empty"]["skip"]
    assert roll["empty"]["cpu"] is None and roll["verdict"]["kind"] in ("insufficient", "none", "cpu", "disk", "network")


def test_phase_empty_message_distinguishes_db_read_from_no_migration(tmp_path):
    """The old message always said "CDM.db not read" whenever phases was empty, even when CDM.db
    was read fine and there's simply no migration in this window (e.g. a run with zero episodes,
    confirmed live 2026-10-22) -- actively misleading for debugging."""
    no_db = RunReport("r3", "target", T0, has_db=False, samples=steady_samples(n=5))
    p1 = payload_of(report.render(no_db, tmp_path / "a.html").read_text(encoding="utf-8"))
    assert "CDM.db not read" in p1["rollup"]["empty"]["phase"]

    db_but_empty = RunReport("r4", "target", T0, has_db=True, samples=steady_samples(n=5))
    p2 = payload_of(report.render(db_but_empty, tmp_path / "b.html").read_text(encoding="utf-8"))
    assert "CDM.db not read" not in p2["rollup"]["empty"]["phase"]
    assert "no migration recorded" in p2["rollup"]["empty"]["phase"]


def test_no_samples_at_all(tmp_path):
    p = payload_of(report.render(RunReport("r", "target", T0), tmp_path / "r.html").read_text(encoding="utf-8"))
    assert "No resource samples" in p["rollup"]["empty"]["cpu"]
    assert p["rollup"]["busy"] == [] and p["rollup"]["verdict"]["kind"] == "insufficient"


def test_script_injection_is_escaped(tmp_path):
    r = run_with(1)
    r.episodes[0].network = "</script><script>alert(1)</script>"
    html = report.render(r, tmp_path / "r.html").read_text(encoding="utf-8")
    assert "</script><script>alert(1)" not in html
    assert payload_of(html)["episodes"][0]["info"]["network"] == "</script><script>alert(1)</script>"


def test_render_without_annotate_and_missing_placeholder(tmp_path, monkeypatch):
    r = RunReport("r", "target", T0, samples=steady_samples(n=4))
    assert r.rollup is None
    report.render(r, tmp_path / "a.html")
    assert r.rollup is not None
    bad = tmp_path / "t.html"
    bad.write_text("<html></html>")
    monkeypatch.setattr(report, "TEMPLATE", bad)
    with pytest.raises(ValueError):
        report.render(r, tmp_path / "b.html")


def test_end_to_end_from_seeded_db(tmp_path):
    db = h.make_three_episode_db(tmp_path / "t.db")
    log = tmp_path / "ft.log"
    log.write_text(h.RCLONE_LOG)
    r = harvest.harvest_run("e2e", "target", tmp_path, {}, db_path=db, log_path=log)
    correlate.annotate(r, {})
    p = payload_of(report.render(r, tmp_path / "r.html").read_text(encoding="utf-8"))
    assert len(p["episodes"]) == 3
    assert [e["kind"] for e in p["episodes"]] == ["primary", "retry", "try_again"]
    assert p["episodes"][0]["thr"]["instant"] != [] and p["rollup"]["drives"]["labels"] == ["C:\\"]


def test_data_moved_tile_never_exceeds_its_own_denominator():
    """`total` can be smaller than `transferred` for a real minority of migrations (confirmed live
    2026-10-22: 4 of 173 drive rows checked, one by 672 MB) -- the tile must never read as "moved
    more than attempted", which can't be made sense of regardless of what `total` means here."""
    ep = make_episode(samples=[])
    ep.drive_stats = [ThroughputPoint(kind="drive", migration_id=1, drive="C:\\",
                                      transferred=10 * report.GB, total=4 * report.GB)]
    v = report.build_view(ep, RunReport("r", "target", T0, episodes=[ep]))
    moved_tile = next(t for t in v["tiles"] if t["l"] == "Data moved")
    assert moved_tile["v"] == "10.0 GB"
    assert "10.0 GB attempted" in moved_tile["d"]              # clamped up to bytes_moved, not 4.0


def test_drive_remaining_is_not_reduced_by_already_existing():
    """already_existing is NOT part of `total` (confirmed live 2026-10-22: it's consistently
    10-20x larger than total across every real migration checked -- a separate, cumulative figure
    for the destination drive, not part of what this session selected). `rem` must come from
    total - transferred alone, not total - transferred - already_existing (which would always be
    a large negative number, silently clamped to 0 and hiding a real failed/incomplete amount)."""
    ep = make_episode(samples=[])
    ep.drive_stats = [ThroughputPoint(kind="drive", migration_id=1, drive="C:\\",
                                      transferred=10 * report.GB, total=15 * report.GB,
                                      already_existing=200 * report.GB)]
    v = report.build_view(ep, RunReport("r", "target", T0, episodes=[ep]))
    assert v["drives"]["copied"] == [10.0]
    assert v["drives"]["existed"] == [200.0]
    assert v["drives"]["rem"] == [5.0]                    # 15 - 10, NOT clamped to 0 by the 200 GB existing


def test_fmt_duration():
    assert report.fmt_duration(None) == "n/a"
    assert report.fmt_duration(42) == "42s" and report.fmt_duration(125) == "2m 05s"
    assert report.fmt_duration(3725) == "1h 02m 05s"


def test_bucketize_and_proc_series_sum_pids():
    assert report._bucketize([(0, 2.0), (1, 4.0), (10, 6.0)], 5.0, 3) == [3.0, None, 6.0]
    samples = [proc_sample(T0, pid=1, cpu=10.0), proc_sample(T0, pid=2, cpu=20.0)]
    out = report._proc_series(samples, T0, 10.0, 2, lambda s: s.cpu_pct)
    assert out["DellFileTransferUtil"][0] == 30.0 and out["DellFileTransferUtil"][1] is None
