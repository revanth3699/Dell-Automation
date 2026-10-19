"""Notification-automation feature package: a generic toast-notification -> automation-
flow dispatcher.

- rules.py      -- NotificationRule: what criteria (app identity, heading text) map to
                   which orchestration/role_runner.py SCENARIOS entry. Edit DEFAULT_RULES
                   here to wire up a new toast -> flow mapping.
- state.py      -- the local JSON state-file contract shared between
                   flows/target/reminder_flow.py (writer) and listener.py (reader).
- listener.py   -- the actual polling loop + CLI entry point.
- scheduler.py  -- Windows Task Scheduler registration so listener.py survives a
                   shutdown/reboot and keeps running.
"""
