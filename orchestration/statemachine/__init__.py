"""State-machine driven runner -- see TARGET_STATE_MACHINE.md.

Layout:
- model.py     -- State/Action/Model: the transition table as data (one Model per role).
- observer.py  -- Observation + the two observers (snapshot = one page_source per tick,
                  probe = per-locator find_element fallback).
- scenario.py  -- YAML scenario loading + validation against a Model.
- runner.py    -- the one loop: observe -> policy -> step action -> wait.
- context.py   -- RunContext handed to every action.

Role-specific wiring (which assertions/components back each state) lives in
target_model.py / source_model.py; composite actions in target_actions.py /
source_actions.py. Nothing in this package imports from flows/ except the composite
actions that deliberately reuse the browser sign-in helpers.
"""
