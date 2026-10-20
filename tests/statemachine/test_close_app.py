"""Graceful close at the end of a PASSED run: the app is closed the way a user does and
the process exit is awaited, so Session.close()'s kill finds nothing to kill."""

from __future__ import annotations

from loguru import logger

from orchestration import scenario_runner
from orchestration.statemachine import source_model, target_model
from orchestration.statemachine.context import RunContext
from orchestration.statemachine.model import Action, Model, State, TextMatch


def ctx():
    return RunContext(role="target", run_id="r", session=None, app=object(), coordination=None, log=logger)


class Running:
    """process_exists() answers: running for the first n polls, then gone."""

    def __init__(self, polls_until_gone):
        self.left = polls_until_gone

    def __call__(self, name):
        self.left -= 1
        return self.left >= 0


# ------------------------------------------------------------------ target

class FakeWindow:
    clicks = 0

    def __init__(self, session):
        pass

    def click_close(self):
        FakeWindow.clicks += 1


class FakeShortcut:
    no_thanks = 0

    def __init__(self, session):
        pass

    def click_create_shortcut(self):
        raise AssertionError("must not create a shortcut")

    def click_no_thanks(self):
        FakeShortcut.no_thanks += 1


def target_close(monkeypatch, polls_until_gone, shortcut_shows):
    FakeWindow.clicks, FakeShortcut.no_thanks = 0, 0
    monkeypatch.setattr(target_model, "AppWindow", FakeWindow)
    monkeypatch.setattr(target_model, "DesktopShortcutDialog", FakeShortcut)
    monkeypatch.setattr(target_model, "process_exists", Running(polls_until_gone))
    monkeypatch.setattr(target_model.time, "sleep", lambda s: None)
    shows = iter(shortcut_shows)
    monkeypatch.setattr(target_model.desktop_shortcut_dialog, "is_showing",
                        lambda session, timeout=0.1: next(shows, False))
    return target_model.build(None).get("welcome").action("close_app")


def test_target_clicks_caption_close_and_waits_for_exit(monkeypatch):
    action = target_close(monkeypatch, polls_until_gone=3, shortcut_shows=[])
    action.perform(ctx(), {})
    assert FakeWindow.clicks == 1
    assert FakeShortcut.no_thanks == 0


def test_target_answers_the_shortcut_offer_with_no_thanks(monkeypatch):
    action = target_close(monkeypatch, polls_until_gone=4, shortcut_shows=[False, True])
    action.perform(ctx(), {})
    assert FakeShortcut.no_thanks == 1


def test_target_does_nothing_when_the_app_already_exited(monkeypatch):
    action = target_close(monkeypatch, polls_until_gone=0, shortcut_shows=[])
    action.perform(ctx(), {})
    assert FakeWindow.clicks == 0


def test_close_app_is_on_every_target_screen_but_no_overlay():
    model = target_model.build(None)
    for state in model.states.values():
        assert ("close_app" in state.actions) == (state.layer == "screen"), state.id


# ------------------------------------------------------------------ source

class FakeProgress:
    def __init__(self, session):
        pass

    buttons = 0
    icons = 0
    has_button = True

    def click_close(self):
        if not FakeProgress.has_button:
            raise RuntimeError("no Close button")
        FakeProgress.buttons += 1

    def click_close_after_delay(self):
        self.click_close()

    def click_close_icon(self):
        FakeProgress.icons += 1

    def __getattr__(self, name):          # every other click the model binds
        return lambda *a, **k: None


def source_close(monkeypatch, has_button):
    FakeProgress.buttons, FakeProgress.icons, FakeProgress.has_button = 0, 0, has_button
    monkeypatch.setattr(source_model, "TransferProgressScreen", FakeProgress)
    monkeypatch.setattr(source_model, "process_exists", Running(2))
    monkeypatch.setattr(source_model.time, "sleep", lambda s: None)
    return source_model.build(None).get("migrationPartialTryAgain").action("close_app")


def test_source_uses_the_close_button_when_there_is_one(monkeypatch):
    source_close(monkeypatch, has_button=True).perform(ctx(), {})
    assert (FakeProgress.buttons, FakeProgress.icons) == (1, 0)


def test_source_falls_back_to_the_window_close_icon(monkeypatch):
    source_close(monkeypatch, has_button=False).perform(ctx(), {})
    assert (FakeProgress.buttons, FakeProgress.icons) == (0, 1)


# ------------------------------------------------------------------ runner entry point

def test_graceful_close_failure_is_logged_not_raised():
    def boom(ctx, args):
        raise RuntimeError("still running")

    model = Model(role="t")
    model.add(State("A", "screen", "user", text=TextMatch(all=("a",)),
                    actions={"close_app": Action("close_app", boom)}, next=()))
    scenario_runner._close_app_gracefully(model, ctx())   # Session.close() still runs afterwards
