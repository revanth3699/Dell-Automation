"""type_code retry / stale-code logic in target_model, with the components, assertions
and coordination client faked -- no WinAppDriver, no service."""

from __future__ import annotations

import pytest
from loguru import logger

from orchestration.statemachine import target_model
from orchestration.statemachine.context import RunContext


class FakeCoordination:
    def __init__(self, values):
        self.values = list(values)  # successive answers to wait_for; None = not published yet

    def wait_for(self, run_id, key, timeout):
        value = self.values.pop(0) if self.values else (self.values and self.values[-1])
        if value is None:
            raise TimeoutError("not published")
        if not self.values:
            self.values = [value]  # keep answering the last value
        return value

    def publish(self, run_id, key, value):
        pass


class FakeCodeEntry:
    typed = []

    def __init__(self, session):
        pass

    def enter_code(self, code, box_count=6, timeout=10.0):
        FakeCodeEntry.typed.append(code)

    def click_cancel(self):
        pass


@pytest.fixture
def model(monkeypatch):
    FakeCodeEntry.typed = []
    monkeypatch.setattr(target_model, "PairingCodeEntryScreen", FakeCodeEntry)
    monkeypatch.setattr(target_model.time, "sleep", lambda s: None)
    monkeypatch.setattr(target_model.pairing_code_entry_screen, "is_locked_showing", lambda s, timeout=0.1: False)
    return target_model.build(None)


def ctx_with(values):
    return RunContext(role="target", run_id="r", session=None, app=object(), coordination=FakeCoordination(values),
                      log=logger)


def accepted_after(monkeypatch, n_rejections):
    """_code_accepted() returns False for the first n calls (code rejected), then True."""
    calls = {"n": 0}

    def fake_accepted(ctx, confirm):
        calls["n"] += 1
        return calls["n"] > n_rejections

    monkeypatch.setattr(target_model, "_code_accepted", fake_accepted)


def test_code_accepted_recognises_rejection_message_and_success(monkeypatch):
    from assertions.target import pairing_code_entry_screen as a
    monkeypatch.setattr(target_model.time, "sleep", lambda s: None)
    ctx = ctx_with([])
    monkeypatch.setattr(a, "is_showing", lambda s, timeout=0.1: True)
    monkeypatch.setattr(a, "is_rejected_showing", lambda s, timeout=0.1: True)
    assert target_model._code_accepted(ctx, confirm=5) is False       # red message -> rejected at once
    monkeypatch.setattr(a, "is_showing", lambda s, timeout=0.1: False)
    assert target_model._code_accepted(ctx, confirm=5) is True        # heading gone -> accepted


def test_first_code_accepted(model, monkeypatch):
    accepted_after(monkeypatch, 0)
    model.get("enterCode").action("type_code").perform(ctx_with(["111111"]), {})
    assert FakeCodeEntry.typed == ["111111"]


def test_rejected_code_is_retried_with_the_next_published_code(model, monkeypatch):
    accepted_after(monkeypatch, 1)
    ctx = ctx_with(["111111", "111111", "222222"])
    model.get("enterCode").action("type_code").perform(ctx, {})
    assert FakeCodeEntry.typed == ["111111", "222222"]


def test_stale_code_from_a_previous_run_is_never_typed(model, monkeypatch):
    accepted_after(monkeypatch, 0)
    ctx = ctx_with(["999999", "999999", "123456"])  # 999999 is already on the service at start
    target_model.snapshot_stale_pairing_code(ctx)
    model.get("enterCode").action("type_code").perform(ctx, {})
    assert FakeCodeEntry.typed == ["123456"]


def test_gives_up_after_max_attempts(model, monkeypatch):
    accepted_after(monkeypatch, 99)
    ctx = ctx_with(["1", "2", "3", "4", "5", "6"])
    with pytest.raises(RuntimeError, match="rejected 3 time"):
        model.get("enterCode").action("type_code").perform(ctx, {"attempts": 3})
    assert FakeCodeEntry.typed == ["1", "2", "3"]


def test_explicit_code_is_typed_once_without_retry(model, monkeypatch):
    accepted_after(monkeypatch, 99)
    with pytest.raises(RuntimeError):
        model.get("enterCode").action("type_code").perform(ctx_with([]), {"code": "000000"})
    assert FakeCodeEntry.typed == ["000000"]
