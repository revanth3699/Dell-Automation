"""Signal phrases for components.target.common_dialogs.MigrationPreparationTransition.

Not XPath locators -- this class polls the raw page source for any of these phrases
rather than using a single element locator (see the component's own docstring for why).
Kept in the locators layer anyway since this is still this class's "how to find this
screen" source of truth, just phrase-based instead of XPath-based.
"""

TRANSITION_PHRASES = (
    "we're getting things ready",
    "checking your pc",
    "starting the migration assistant",
)
