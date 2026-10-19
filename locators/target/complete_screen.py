"""Locators for components.target.complete_screen.CompleteScreen -- click-target locators.
BACK_TO_SUMMARY_LINK_LOCATOR is genuinely dual-purpose (clicked AND used as the
distinguishing existence check in assertions/target/complete_screen.py, which imports
it from here rather than duplicating it -- see CLAUDE.md on dual-purpose elements).

Verified against source, not live: rebit TargetPc.UI
web/src/screens/results/CompleteView.tsx. The header action is a StagePanel
actionLabel t('Complete_BackToSummary') = "Back to summary" with a leading aria-hidden
arrow icon, rendered by components/stage/StagePanelHeader.tsx as a DDSLink -- a link,
hence //*. "Open a PDF report" is a DDSLink in the right card labelled
t('Complete_OpenPdfCtaTitle') (Resources/Resources.resx); it stays rendered but inert
(aria-disabled) until state.canOpenPdf is true.
"""

BACK_TO_SUMMARY_LINK_LOCATOR = ("xpath", '//*[@Name="Back to summary"]')
OPEN_PDF_LINK_LOCATOR = ("xpath", '//*[@Name="Open a PDF report"]')
