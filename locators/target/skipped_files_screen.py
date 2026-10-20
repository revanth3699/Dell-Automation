"""Locators for components.target.skipped_files_screen.SkippedFilesScreen -- click-target
locators only. The heading assertion locator lives in
assertions/target/skipped_files_screen.py instead.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/results/SkippedFilesView.tsx (Resources/Resources.resx):
- RETRY_BUTTON_LOCATOR: the right card is a MigrateNowCard whose IconButton
  (components/common/IconButton.tsx, a DDSButton with aria-label) carries
  ariaLabel=t('Buttons_Retry') = "Retry" when state.retryVisible is true. The card's
  visible title is SkippedFiles_RetryCtaTitle ("Try transferring these files again"),
  a heading, not the button's Name.
- FINISH_BUTTON_LOCATOR: same IconButton with ariaLabel=t('Buttons_Finish') = "Finish"
  in the cancelled-run and network-lost cases (retryVisible false / networkLost true).
  Only one of Retry/Finish is rendered at a time.
- GO_TO_SUMMARY_LINK_LOCATOR: the StagePanel header action, actionLabel
  t('SkippedFiles_GoToSummary') = "Go to summary" with a leading aria-hidden arrow,
  rendered by components/stage/StagePanelHeader.tsx as a DDSLink -- hence //*.
"""

RETRY_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Retry"]')
FINISH_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Finish"]')
GO_TO_SUMMARY_LINK_LOCATOR = ("xpath", '//*[@Name="Go to summary"]')
