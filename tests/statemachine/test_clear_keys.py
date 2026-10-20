"""A reused run id must start clean: each role deletes its own keys on the coordination
service before publishing anything (confirmed need, 2026-10-20: a stale outcome from the
previous run 651 stalled the Source's second-round condition)."""

from __future__ import annotations

import requests
from loguru import logger

from coordination_service import app as service
from orchestration import scenario_runner
from orchestration.statemachine import peer
from orchestration.statemachine.context import RunContext
from orchestration.statemachine.scenario import parse_scenario


def test_service_deletes_one_key_and_tolerates_a_missing_one(monkeypatch):
    monkeypatch.setattr(service, "_state", {})
    monkeypatch.setattr(service, "_save_state", lambda state: None)
    service.publish("r", "target_outcome", service.PublishBody(value="partial"))
    service.publish("r", "source_state", service.PublishBody(value="finished"))
    assert service.delete_value("r", "target_outcome") == {"run_id": "r", "key": "target_outcome", "removed": True}
    assert service.delete_value("r", "target_outcome")["removed"] is False
    assert service.get_value("r", "source_state")["value"] == "finished"   # other keys untouched


class FakeCoordination:
    def __init__(self, supported=True):
        self.supported = supported
        self.cleared = []

    def clear(self, run_id, key, timeout=10.0):
        self.cleared.append(key)
        return self.supported


def test_clear_own_keys_reports_support():
    coordination = FakeCoordination()
    ctx = RunContext(role="source", run_id="r", session=None, app=object(), coordination=coordination, log=logger)
    assert peer.clear_own_keys(ctx, ["source_state", "pairing_code"]) is True
    assert coordination.cleared == ["source_state", "pairing_code"]


def test_clear_own_keys_falls_back_on_an_old_service():
    ctx = RunContext(role="source", run_id="r", session=None, app=object(), coordination=FakeCoordination(False),
                     log=logger)
    assert peer.clear_own_keys(ctx, ["source_state"]) is False   # no exception: stale detection still applies


def test_clear_own_keys_survives_a_network_error():
    class Down:
        def clear(self, run_id, key, timeout=10.0):
            raise requests.exceptions.ConnectionError("down")

    ctx = RunContext(role="target", run_id="r", session=None, app=object(), coordination=Down(), log=logger)
    assert peer.clear_own_keys(ctx, ["target_state"]) is False


def test_each_role_only_clears_what_it_publishes():
    script = parse_scenario({"name": "t", "roles": {"target": {"steps": [
        {"at": "A", "do": "publish", "args": {"key": "target_outcome", "value": "partial"}},
        {"at": "A", "do": "wait_for_peer", "args": {"key": "source_hint", "state": "x"}},
    ]}}}).role("target")
    _waited, published = scenario_runner.coordination_keys(script)
    assert published == {"target_outcome"}
    assert "source_hint" not in published   # a key this role only reads is never deleted by it
