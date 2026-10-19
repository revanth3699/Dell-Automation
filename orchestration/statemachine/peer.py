"""Peer sync through the Coordination Service -- the ONLY channel between the Target and
Source scripts (CLAUDE.md "Both machines, one channel").

Each side publishes its own progress under its key (target_state / source_state) and
waits for the other side's value. attach_peer_actions() gives every State in a Model two
generic actions so any scenario step can sync from anywhere:

    - do: publish        args: {value: migrating}            # "I am here"
    - do: wait_for_peer  args: {state: migrating, timeout: 600, key: target_state}

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


def wait_for_peer_state(ctx, key: str, wanted: str, timeout: float) -> None:
    """Polls until key == wanted. CoordinationClient.wait_for() returns the first value
    present (not necessarily the wanted one), so it is called repeatedly with short
    timeouts until the value matches."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        remaining = deadline - time.monotonic()
        try:
            value = ctx.coordination.wait_for(ctx.run_id, key, timeout=min(10.0, max(1.0, remaining)))
        except (TimeoutError, requests.exceptions.RequestException):
            value = None
        if value == wanted:
            ctx.log.success(f"peer reported {key}={wanted}")
            return
        time.sleep(2.0)
    raise TimeoutError(f"peer never reported {key}={wanted} within {timeout:.0f}s")


def attach_peer_actions(model: Model, own_key: str, peer_key: str) -> None:
    """Adds `publish` and `wait_for_peer` to every state (without overriding a state's
    own action of the same name)."""

    def do_publish(ctx, args) -> None:
        publish(ctx, own_key, str(args.get("value", "")))

    def do_wait(ctx, args) -> None:
        wait_for_peer_state(ctx, str(args.get("key", peer_key)), str(args["state"]), float(args.get("timeout", 600.0)))

    for state in model.states.values():
        state.actions.setdefault("publish", Action("publish", do_publish, description=f"publish {own_key}=<value>", idempotent=False))
        state.actions.setdefault("wait_for_peer", Action("wait_for_peer", do_wait, idempotent=False,
                                                         description=f"wait until {peer_key}=<state>"))
