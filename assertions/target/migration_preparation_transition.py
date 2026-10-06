"""Expected signal phrases for components.target.common_dialogs.MigrationPreparationTransition.

Confirmed via user-supplied screenshots (2026-10-05). Moved here from locators/ (2026-10-07):
unlike every other locator in this codebase, these were never an XPath -- the component polls
the raw page source for plain-text containment instead of looking up one element -- so they
belong with the other expected-text constants in assertions/, not the element-finder layer.
Same centralization rationale as assertions/target/error_banner.py: one copy of each string.
"""

TRANSITION_PHRASES = (
    "we're getting things ready",
    "checking your pc",
    "starting the migration assistant",
)
