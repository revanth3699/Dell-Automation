"""Expected signal phrases for the Target migration-preparation transition screens,
plus the poll+assert function that uses them. Confirmed via user-supplied screenshots
(2026-10-05). Unlike every other locator in this codebase, these were never an XPath --
this polls the raw page source for plain-text containment instead of looking up one
element -- so this lives here, in assertions/, as a plain function called directly from
flows/ (per explicit user direction, 2026-10-14).
"""

import time

TRANSITION_PHRASES = (
    "we're getting things ready",
    "checking your pc",
    "starting the migration assistant",
)


def wait_until_any_showing(session, timeout: float, poll_interval: float = 1.0):
    """Returns the matched phrase once any of them appears within timeout, or None
    if the timeout expires first. Not every run necessarily shows one specific
    screen, and exact timing relative to UAC can vary, so rather than requiring one
    exact screen, this polls the raw page source (one /source call per iteration, not
    a per-candidate locator lookup) for ANY of the known transition phrases -- the
    concrete, pollable signal that UAC was approved and something moved forward.
    """
    deadline = time.monotonic() + timeout
    while True:
        try:
            source = session.page_source.lower()
        except Exception:
            source = ""
        for text in TRANSITION_PHRASES:
            if text in source:
                return text
        if time.monotonic() >= deadline:
            return None
        time.sleep(poll_interval)
