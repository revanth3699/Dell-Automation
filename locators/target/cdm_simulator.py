"""Locators for components.target.cdm_simulator.CdmSimulatorWindow -- the CDM Simulator
WPF app ("CDMSimulatorUI") that mimics Dell SupportAssist's role in launching the Target
PC UI app and auto-responding to its backend Init/Job/Migration/Completed protocol
messages, used in place of real SupportAssist integration (not built yet). Confirmed
from a user-supplied screenshot (2026-10-12).

The "Exe:" textbox has no confirmed accessible Name (a plain WPF TextBox next to a
separate "Exe:" Label, not independently confirmed live) -- found positionally instead
(the first Edit control in the window), same convention already used by
components/target/pairing_code_entry_screen.py for its own unconfirmed WPF textboxes.
Not included as a locator constant here for that reason -- see
CdmSimulatorWindow._find_exe_textbox().

The Launch button and Auto-respond checkbox's visible Content text IS their accessible
Name by default WPF UI Automation behavior (no explicit AutomationProperties.Name set)
-- the same assumption already relied on throughout this codebase for WPF/WinUI
buttons (e.g. "Finish", "Back to Home") and confirmed correct every time it was later
verified live.
"""

LAUNCH_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Launch"]')
AUTO_RESPOND_CHECKBOX_LOCATOR = ("xpath", '//CheckBox[@Name="Auto-respond"]')
