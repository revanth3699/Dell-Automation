"""Locators for components.target.cdm_simulator.CdmSimulatorWindow -- the CDM Simulator
WPF app ("CDMSimulatorUI") that mimics Dell SupportAssist's role in launching the Target
PC UI app and auto-responding to its backend Init/Job/Migration/Completed protocol
messages, used in place of real SupportAssist integration (not built yet). Confirmed
from a user-supplied screenshot (2026-10-12).

Bug fixed here, confirmed via a live UI-tree dump (2026-10-12): unlike the Target PC
UI's WebView2/React-rendered controls (where visible button text IS the accessible
Name), this app's WPF controls all report their generic class name as Name (e.g.
Name="Button" for every single button) -- the real, stable identifier here is
AutomationId instead, confirmed via a raw /source dump of the live window:
LaunchTargetPcButton, AutoRespondCheckBox, and TargetPcLocationText (the "Exe:"
textbox -- also confirmed via the same dump, so no longer found positionally).
"""

LAUNCH_BUTTON_LOCATOR = ("xpath", '//Button[@AutomationId="LaunchTargetPcButton"]')
AUTO_RESPOND_CHECKBOX_LOCATOR = ("xpath", '//CheckBox[@AutomationId="AutoRespondCheckBox"]')
EXE_TEXTBOX_LOCATOR = ("xpath", '//Edit[@AutomationId="TargetPcLocationText"]')
