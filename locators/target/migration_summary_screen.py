"""Locators for components.target.migration_summary_screen.MigrationSummaryScreen --
click-target locator only. The heading assertion locator lives in
assertions/target/migration_summary_screen.py instead.

Bug fixed here, confirmed directly by the user (2026-10-09) via live screenshots:
this screen also has a "Finish" link (top right) -- the actual next step in the real
flow. The "here" link used to be clicked instead; that was wrong -- clicking "here"
doesn't advance to the real completion screen ("Your migration is now complete"),
"Finish" does.
"""

FINISH_LINK_LOCATOR = ("xpath", '//*[@Name="Finish"]')
