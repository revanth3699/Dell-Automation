import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from benchmark import correlate, harvest, paths, report
from utils import environment


def make_ctx(tmp_path, monkeypatch, run_id="rid"):
    monkeypatch.setattr(paths, "OUTPUT_ROOT", tmp_path)
    return SimpleNamespace(run_id=run_id, role="target", scratch={}, env={}, log=MagicMock())


def fake_popen(monkeypatch, wait_side_effect=None):
    proc = MagicMock(pid=4242)
    proc.wait.side_effect = wait_side_effect
    popen = MagicMock(return_value=proc)
    monkeypatch.setattr(environment.subprocess, "Popen", popen)
    return popen, proc


def test_registration_and_resolve():
    assert "start_benchmark" in environment.STEPS and "stop_benchmark_report" in environment.STEPS
    assert environment.resolve("start_benchmark") is environment.start_benchmark
    assert environment.resolve("stop_benchmark_report") is environment.stop_benchmark_report


def test_start_spawns_sampler_and_stores_state(tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path, monkeypatch)
    stale = tmp_path / "rid"
    stale.mkdir()
    (stale / "STOP_target").write_text("stale")
    popen, proc = fake_popen(monkeypatch)
    environment.start_benchmark(ctx)
    cmd = popen.call_args.args[0]
    assert cmd[1:3] == ["-m", "benchmark.resource_sampler"] and "--stop-file" in cmd
    assert cmd[cmd.index("--run-id") + 1] == "rid" and cmd[cmd.index("--role") + 1] == "target"
    state = ctx.scratch["benchmark"]
    assert state["proc"] is proc and state["out"] == tmp_path / "rid"
    assert not state["stop_file"].exists()                       # stale stop file cleared
    assert "4242" in ctx.log.info.call_args.args[0]
    state["log_file"].close()


def test_start_does_not_raise_when_spawn_fails(tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path, monkeypatch)
    monkeypatch.setattr(environment.subprocess, "Popen", MagicMock(side_effect=OSError("no python")))
    environment.start_benchmark(ctx)
    assert "benchmark" not in ctx.scratch and ctx.log.warning.called


def stub_pipeline(monkeypatch, harvest_error=None, render_error=None):
    calls = []

    def fake_harvest(run_id, role, out, env):
        calls.append("harvest")
        if harvest_error:
            raise harvest_error
        return SimpleNamespace(run_id=run_id)

    monkeypatch.setattr(harvest, "harvest_run", fake_harvest)
    monkeypatch.setattr(correlate, "annotate", lambda rr, env: calls.append("annotate"))

    def fake_render(rr, out):
        calls.append("render")
        if render_error:
            raise render_error
        return out

    monkeypatch.setattr(report, "render", fake_render)
    return calls


def test_stop_touches_stop_file_harvests_and_renders(tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path, monkeypatch)
    _, proc = fake_popen(monkeypatch)
    environment.start_benchmark(ctx)
    calls = stub_pipeline(monkeypatch)
    environment.stop_benchmark_report(ctx)
    assert ctx.scratch["benchmark"]["stop_file"].read_text() == "stop"
    proc.wait.assert_called_once()
    assert calls == ["harvest", "annotate", "render"]
    assert str(tmp_path / "rid" / "report_target.html") in ctx.log.success.call_args.args[0]


def test_stop_terminates_a_sampler_that_will_not_exit(tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path, monkeypatch)
    _, proc = fake_popen(monkeypatch, wait_side_effect=[subprocess.TimeoutExpired("x", 1), None])
    environment.start_benchmark(ctx)
    stub_pipeline(monkeypatch)
    environment.stop_benchmark_report(ctx)
    proc.terminate.assert_called_once()
    proc.kill.assert_not_called()


def test_stop_kills_when_terminate_also_hangs(tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path, monkeypatch)
    t = subprocess.TimeoutExpired("x", 1)
    _, proc = fake_popen(monkeypatch, wait_side_effect=[t, t])
    environment.start_benchmark(ctx)
    stub_pipeline(monkeypatch)
    environment.stop_benchmark_report(ctx)
    proc.kill.assert_called_once()


def test_stop_never_raises_when_harvest_throws(tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path, monkeypatch)
    fake_popen(monkeypatch)
    environment.start_benchmark(ctx)
    stub_pipeline(monkeypatch, harvest_error=RuntimeError("db exploded"))
    assert environment.stop_benchmark_report(ctx) is None
    assert "db exploded" in ctx.log.warning.call_args.args[0]


def test_stop_never_raises_when_render_throws_or_nothing_started(tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path, monkeypatch)
    stub_pipeline(monkeypatch, render_error=ValueError("template"))
    assert environment.stop_benchmark_report(ctx) is None           # no start_benchmark ever ran
    assert ctx.log.warning.called


def test_stop_survives_broken_logger_and_sampler_stop_errors(tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path, monkeypatch)
    ctx.log.warning.side_effect = RuntimeError("logger down")
    stub_pipeline(monkeypatch, harvest_error=RuntimeError("x"))
    assert environment.stop_benchmark_report(ctx) is None
    ctx2 = make_ctx(tmp_path, monkeypatch, "rid2")
    ctx2.scratch["benchmark"] = {"stop_file": tmp_path / "nonexistent_dir" / "STOP", "proc": None}
    stub_pipeline(monkeypatch)
    assert environment.stop_benchmark_report(ctx2) is None
    assert ctx2.log.warning.called


def test_stop_does_not_swallow_keyboard_interrupt(tmp_path, monkeypatch):
    ctx = make_ctx(tmp_path, monkeypatch)
    stub_pipeline(monkeypatch, harvest_error=KeyboardInterrupt())
    with pytest.raises(KeyboardInterrupt):
        environment.stop_benchmark_report(ctx)
