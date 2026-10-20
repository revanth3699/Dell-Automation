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

# Added 2026-10-19 (verified against rebit source, not live): ResultsSummaryView.tsx's
# subtitle ends with a <button className=subtitleLink> labelled ResultsSummary_Here ("View
# the details") -- the only way into the details (skipped-files screen when anything was
# not transferred, otherwise the Complete screen). This replaces the old "here" link copy.
VIEW_DETAILS_LINK_LOCATOR = ("xpath", '//*[@Name="View the details"]')
