"""Expected heading text + locator + assertion function for
components.target.common_dialogs.SignInFailedDialog. Never a click target, so it lives
here rather than in locators/ -- per explicit user direction (2026-10-14).

Bug fixed here, confirmed directly by the user via a live screenshot (2026-10-14): the
real heading is "We couldn't sign you in", NOT "There was a problem signing in" -- the
latter was only ever inferred from a reference flow diagram ("dell screens flow.pdf",
2026-10-05), never independently confirmed live until now. Body text confirmed too:
"The process may have been interrupted or taken too long to complete. Sign-in failed.
Please try again. Retry to open a new window and try again." -- not currently checked
(only the heading is), but recorded here for reference.

Bug fixed here AGAIN, confirmed live (2026-10-14): even after that correction,
is_showing() STILL always returned False against a live run where the dialog was
confirmed visibly showing the whole time (via screenshot).

Widened here YET AGAIN (2026-10-14): the user confirmed directly that the ORIGINAL
heading, "There was a problem signing in" (the very first committed version of this
locator, unchanged across this project's entire git history up to this point), used to
be detected and clicked correctly in an earlier live run, before this file was changed
today. That directly conflicts with today's screenshot, which unambiguously shows the
real heading as "We couldn't sign you in" -- materially different wording, not just a
punctuation/quote variant. Rather than assume one claim is wrong, this now races BOTH
phrasings: it's plausible Dell's app shows different wording for different failure
causes (e.g. a network/backend error vs. this project's own deliberate OTP-cancel
negative-path check, which is what every run's attempt 0 actually triggers). Matches on
short, apostrophe-free, distinctive substrings of each ("sign you in" / "problem signing
in") rather than either full exact string, so neither is vulnerable to an invisible
curly-quote/whitespace mismatch the way the original exact-match attempts were.
"""

from assertions.common import text_exists

HEADING_TEXT = "We couldn't sign you in"
SIGN_IN_FAILED_HEADING_LOCATOR = (
    "xpath", '//*[contains(@Name, "sign you in") or contains(@Name, "problem signing in")]'
)


def is_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(session, SIGN_IN_FAILED_HEADING_LOCATOR, "SignInFailedHeading", timeout=timeout)
