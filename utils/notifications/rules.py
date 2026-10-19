"""Generic notification -> automation-flow dispatch rules for
utils/notifications/listener.py.

Each NotificationRule says: "if a real toast notification matches these criteria, treat
it as the trigger to resume whatever pending reminder is waiting." Per explicit user
direction (2026-10-19): "event listener keeps an eye on toast notification, event
handler checks on condition (example: notification title), and then triggers an
automation flow" -- this is that condition-check layer, kept separate from the polling
mechanics in listener.py so a new rule can be added here without touching that code.

Note on where the ACTUAL scenario-to-run comes from: it is NOT read off the rule here --
it's recorded on the pending state file itself at write time (see state.py's
write_pending()), chosen by whoever set the reminder (flows/target/reminder_flow.py).
A rule's job is only to decide WHETHER a given real notification counts as "the"
trigger event at all (by app identity and/or heading text) -- matching a rule causes
listener.py to resume every currently-pending reminder, each using its own recorded
scenario. This keeps the two concerns independent: "did something worth reacting to just
happen" (rules.py) vs. "what should run when it does" (each pending reminder's own
state).
"""

from dataclasses import dataclass
from typing import Optional

# Confirmed live this session via get_notifications_async() on this machine: this test
# machine's real, already-installed Dell SupportAssist app posts notifications under
# this AUMID. A strong lead, NOT a confirmed match for the actual migration-reminder
# notification's identity -- confirm live once the real reminder has been seen to fire.
DEFAULT_DELL_AUMID = "DellInc.DellSupportAssistforPCs_htrsf667h5kn2!App"


@dataclass(frozen=True)
class NotificationRule:
    name: str  # human-readable, used only in log lines
    aumid: Optional[str] = None  # exact app_user_model_id match; None = any app
    heading_contains: Optional[str] = None  # substring match against the notification's
                                             # own heading text; None = any heading

    def matches(self, aumid: str, heading: str) -> bool:
        if self.aumid is not None and aumid != self.aumid:
            return False
        if self.heading_contains is not None and self.heading_contains not in heading:
            return False
        return True


# PLACEHOLDER, not a confirmed production value (2026-10-19): narrowed from an earlier
# aumid-only, heading_contains=None rule (which matched ANY notification from Dell
# SupportAssist -- too broad for real use, since that app posts plenty of unrelated
# notifications, e.g. "Check your PC Setup", confirmed seen on this machine). "Support
# Assist" is a stand-in heading substring for testing the rule's discrimination (a
# notification from the right app with the WRONG heading must NOT match), not the real
# migration-reminder notification's actual text -- that still needs live confirmation.
# Narrow or replace this once the real heading is known.
DEFAULT_RULES: list[NotificationRule] = [
    NotificationRule(name="dell_support_assist_reminder", aumid=DEFAULT_DELL_AUMID, heading_contains="Support Assist"),
]


def find_matching_rule(rules: list[NotificationRule], aumid: str, heading: str) -> Optional[NotificationRule]:
    for rule in rules:
        if rule.matches(aumid, heading):
            return rule
    return None
