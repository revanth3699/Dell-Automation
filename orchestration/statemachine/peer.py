"""Peer sync through the Coordination Service -- the ONLY channel between the Target and
Source scripts (CLAUDE.md "Both machines, one channel").

Each side publishes its own progress under its key (target_state / source_state) and
waits for the other side's value. attach_peer_actions() gives every State in a Model two
generic actions so any scenario step can sync from anywhere:

    - do: publish        args: {value: migrating}            # "I am here"
    - do: wait_for_peer  args: {state: migrating, timeout: 600, key: target_state}
    - do: wait_for_peer  args: {state: [finished, failed]}   # either value

The runner itself publishes <role>_state=finished or failed when a role's script ends
(orchestration/scenario_runner.py), so one side can hold its app open until the other
is done -- e.g. the Source waits for the Target before closing.

Values are free-form strings agreed between the two role scripts of one scenario.
"""

from __future__ import annotations

import time

import requests

from orchestration.statemachine.model import Action, Model

TARGET_STATE_KEY = "target_state"
SOURCE_STATE_KEY = "source_state"


def publish(ctx, key: str, value: str) -> None:
    """Best-effort publish -- a coordination blip must not fail a UI step."""
    try:
        ctx.coordination.publish(ctx.run_id, key, value)
        ctx.log.info(f"published {key}={value}")
    except requests.exceptions.RequestException as exc:
        ctx.log.warning(f"could not publish {key}={value}: {exc}")


def snapshot_stale_value(ctx, key: str) -> None:
    """Records the value `key` already holds when this run starts, so wait_for_peer_state()
    will not accept it until it has changed. Systemic fix for reused run ids (2026-10-20:
    the previous run's pairing code was read within 80 ms and typed): the coordination
    service keeps values per run id forever, so anything present before we start is
    suspect until the peer writes something new."""
    try:
        value = ctx.coordination.wait_for(ctx.run_id, key, timeout=1.0)
    except (TimeoutError, requests.exceptions.RequestException):
        return
    ctx.scratch.setdefault("stale_values", {})[key] = str(value)
    ctx.log.warning(f"{key}={value} was already on the coordination service for run {ctx.run_id} -- "
                    "ignoring it until the peer publishes something new")


def wait_for_peer_state(ctx, key: str, wanted, timeout: float) -> None:
    """Polls until key == wanted (or is one of `wanted`, when a list is given). CoordinationClient.wait_for() returns the first value
    present (not necessarily the wanted one), so it is called repeatedly with short
    timeouts until the value matches."""
    wanted_set = {str(w) for w in (wanted if isinstance(wanted, (list, tuple, set)) else [wanted])}
    stale = ctx.scratch.get("stale_values", {}).get(key)
    changed = False
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        try:
            value = ctx.coordination.wait_for(ctx.run_id, key, timeout=min(10.0, max(1.0, remaining)))
        except (TimeoutError, requests.exceptions.RequestException):
            value = None
        if value is not None and str(value) != stale:
            changed = True
        if value in wanted_set and (changed or stale is None):
            ctx.log.success(f"peer reported {key}={value}")
            return
        time.sleep(2.0)
    raise TimeoutError(f"peer never reported {key} in {sorted(wanted_set)} within {timeout:.0f}s")


def attach_peer_actions(model: Model, own_key: str, peer_key: str) -> None:
    """Adds `publish` and `wait_for_peer` to every state (without overriding a state's
    own action of the same name)."""

    def do_publish(ctx, args) -> None:
        publish(ctx, own_key, str(args.get("value", "")))

    def do_wait(ctx, args) -> None:
        wait_for_peer_state(ctx, str(args.get("key", peer_key)), args["state"], float(args.get("timeout", 600.0)))

    for state in model.states.values():
        state.actions.setdefault("publish", Action("publish", do_publish, description=f"publish {own_key}=<value>", idempotent=False))
        state.actions.setdefault("wait_for_peer", Action("wait_for_peer", do_wait, idempotent=False,
                                                         description=f"wait until {peer_key}=<state>"))
