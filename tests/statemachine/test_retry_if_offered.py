"""full_transfer's retry round: retry_if_offered clicks Retry only when the skipped-files
card offers it, and otherwise lets the scenario fall through to Go to summary."""

from __future__ import annotations

from loguru import logger

from orchestration.statemachine import target_model
from orchestration.statemachine.context import RunContext


class FakeSkipped:
    clicks = 0

    def __init__(self, session):
        pass

    def click_retry(self):
        FakeSkipped.clicks += 1

    def click_finish(self):
        raise AssertionError("Finish must not be clicked by retry_if_offered")

    def click_go_to_summary(self):
        raise AssertionError("Go to summary must not be clicked by retry_if_offered")


def build(monkeypatch, offered: bool):
    FakeSkipped.clicks = 0
    monkeypatch.setattr(target_model, "SkippedFilesScreen", FakeSkipped)
    monkeypatch.setattr(target_model.skipped_files_screen, "retry_is_offered", lambda session, timeout=2.0: offered)
    model = target_model.build(None)
    ctx = RunContext(role="target", run_id="r", session=None, app=object(), coordination=None, log=logger)
    return model.get("skippedFiles").action("retry_if_offered"), ctx


def test_clicks_retry_when_the_card_offers_it(monkeypatch):
    action, ctx = build(monkeypatch, offered=True)
    action.perform(ctx, {})
    assert FakeSkipped.clicks == 1
    assert "migrating" in action.expect


def test_moves_on_when_only_finish_is_offered(monkeypatch):
    action, ctx = build(monkeypatch, offered=False)
    action.perform(ctx, {})  # no exception: the next full_transfer steps fall through
    assert FakeSkipped.clicks == 0
    assert "skippedFiles" in action.expect  # staying put is an expected outcome, not an unexpected state
