"""Locators for components.target.pairing_code_entry_screen.PairingCodeEntryScreen --
click-target locator only. The heading assertion locator + status assertions live in
assertions/target/pairing_code_entry_screen.py instead; the 6 code-entry boxes are found
positionally (//Edit) by the component itself, not via a named locator here.

Added 2026-10-19 (verified against rebit source, not live): EnterCodeStage.tsx is built on
the shared StageCard frame, whose top-right cancel control is a <button className=cancelLink>
labelled with the default Buttons_Cancel ("Cancel") plus an aria-hidden "x" icon, wired to
Channels.enterCodeCancel. //* rather than //Button to match the convention already used for
StageCard's other link-styled buttons (locators/target/migration_summary_screen.py's Finish).
"""

CANCEL_LINK_LOCATOR = ("xpath", '//*[@Name="Cancel"]')
