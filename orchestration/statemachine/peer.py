"""Peer sync through the Coordination Service -- the ONLY channel between the Target and
Source scripts (CLAUDE.md "Both machines, one channel").

Each side publishes its own progress under its key (target_state / source_state) and
waits for the other side's value. attach_peer_actions() gives every State in a Model two
generic actions so any scenario step can sync from anywhere:

    - do: publish        args: {value: migrating}            # "I am here"
    - do: publish        args: {key: target_outcome, value: partial}   # any other key
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
FAILED = "failed"


class PeerFailed(Exception):
    """The other machine's script ended with <peer>_state=failed: there is nothing left
    to wait for on this side."""


def peer_state_key(ctx) -> str:
    return SOURCE_STATE_KEY if ctx.role == "target" else TARGET_STATE_KEY


def peer_failed(ctx) -> bool:
    """Non-blocking read of the peer's state: True once it reports failed in THIS run.
    A `failed` left over from an earlier run with the same id (the stale snapshot) does
    not count until some other value has been seen, which the peer's own
    <role>_state=started publish guarantees early in its run."""
    key = peer_state_key(ctx)
    try:
        value = ctx.coordination.wait_for(ctx.run_id, key, timeout=1.0)
    except (TimeoutError, requests.exceptions.RequestException):
        return False
    stale = ctx.scratch.get("stale_values", {}).get(key)
    if value is not None and str(value) != stale:
        _stale_cleared(ctx, key)
        stale = None
    return str(value) == FAILED and stale is None


def raise_if_peer_failed(ctx) -> None:
    if peer_failed(ctx):
        raise PeerFailed(f"the {'source' if ctx.role == 'target' else 'target'} script reported failed")


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


def _stale_cleared(ctx, key: str) -> None:
    """The peer has published something new under `key` this run: from now on any
    value is current, in every later wait and check."""
    ctx.scratch.get("stale_values", {}).pop(key, None)


def wait_for_peer_state(ctx, key: str, wanted, timeout: float) -> None:
    """Polls until key == wanted (or is one of `wanted`, when a list is given)."""
    wait_for_state_value(ctx, key, wanted, timeout)


def wait_for_state_value(ctx, key: str, wanted, timeout: float) -> str:
    """Polls until `key` holds one of `wanted` and returns that value.
    CoordinationClient.wait_for() returns the first value present (not necessarily a
    wanted one), so it is called repeatedly with short timeouts until the value
    matches. A value recorded as stale at run start is ignored until it changes."""
    wanted_set = {str(w) for w in (wanted if isinstance(wanted, (list, tuple, set)) else [wanted])}
    deadline = time.monotonic() + timeout
    watch_peer = key != peer_state_key(ctx)   # waiting for the peer's own state handles `failed` itself
    while time.monotonic() < deadline:
        if watch_peer:
            raise_if_peer_failed(ctx)
        remaining = deadline - time.monotonic()
        try:
            value = ctx.coordination.wait_for(ctx.run_id, key, timeout=min(10.0, max(1.0, remaining)))
        except (TimeoutError, requests.exceptions.RequestException):
            value = None
        # Confirmed live (2026-10-20, run 651 reused): the "stale value has changed" fact
        # must outlive this call. The Source's first wait saw started -> partial and
        # accepted; the group condition's second wait saw only partial, equal to the
        # previous run's stale value, and hung. Once a key has changed it stays cleared.
        stale = ctx.scratch.get("stale_values", {}).get(key)
        if value is not None and str(value) != stale:
            _stale_cleared(ctx, key)
            stale = None
        if value in wanted_set and stale is None:
            ctx.log.success(f"coordination service reports {key}={value}")
            return str(value)
        time.sleep(2.0)
    raise TimeoutError(f"{key} never became one of {sorted(wanted_set)} within {timeout:.0f}s")


def resolve_condition(ctx, when: dict) -> tuple[bool, str]:
    """A step group's `when:` clause -- waits until `key` holds one of `among`, then
    tells whether it is the value `is`. Both roles can branch on the same published
    fact (e.g. the Target's migration outcome) without any other channel."""
    value = wait_for_state_value(ctx, str(when["key"]), when["among"], float(when.get("timeout", 600.0)))
    return value == str(when["is"]), value


def attach_peer_actions(model: Model, own_key: str, peer_key: str) -> None:
    """Adds `publish` and `wait_for_peer` to every state (without overriding a state's
    own action of the same name)."""

    def do_publish(ctx, args) -> None:
        publish(ctx, str(args.get("key", own_key)), str(args.get("value", "")))

    def do_wait(ctx, args) -> None:
        wait_for_peer_state(ctx, str(args.get("key", peer_key)), args["state"], float(args.get("timeout", 600.0)))

    for state in model.states.values():
        state.actions.setdefault("publish", Action("publish", do_publish, description=f"publish {own_key}=<value>", idempotent=False))
        state.actions.setdefault("wait_for_peer", Action("wait_for_peer", do_wait, idempotent=False,
                                                         description=f"wait until {peer_key}=<state>"))
