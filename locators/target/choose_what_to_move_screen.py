"""Locators for components.target.choose_what_to_move_screen.ChooseWhatToMoveScreen --
click-target locators only. The heading/warning assertion locators live in
assertions/target/choose_what_to_move_screen.py instead. The "Migrate now" arrow button
is NOT here -- it already exists as
locators/target/transfer_receive_screen.py's BRING_EVERYTHING_OVER_BUTTON_LOCATOR.

Verified against source, not live (rebit TargetPc.UI, Resources/Resources.resx):
- LET_ME_CHOOSE_LINK_LOCATOR: screens/choose-what-to-move/ChooseFilesLinkCard.tsx, a
  DDSLink labelled t('ChooseWhatToMove_ChooseCustomCard') = "Let me choose what to
  transfer" (trailing arrow is an aria-hidden SVG, so it does not alter the Name).
- GO_BACK_LINK_LOCATOR: screens/choose-what-to-move/FileSelectionTreeCard.tsx, a DDSLink
  labelled t('Buttons_GoBack') = "Go back".
- SELECT_ALL_CHECKBOX_LOCATOR: FileSelectionTreeCard.tsx renders a DDSCheckbox with NO
  label/aria-label (DDSCheckbox's props are plain InputHTMLAttributes -- see
  vendor/dds-react/components/checkbox/Checkbox.types.d.ts); the "Select all files and
  settings" text (ChooseWhatToMove_SelectAllLabel) is a sibling <span>, not an
  associated <label>, so the checkbox's own accessible Name is expected to be EMPTY and
  cannot be targeted by Name. It is the first checkbox in document order in tree mode
  (header row precedes the tree's per-node checkboxes; the Drive Mapping modal's
  checkboxes exist only while that modal is open), hence the positional locator.
  UNVERIFIED: whether WinAppDriver resolves this positional XPath as intended -- confirm
  live, and fall back to clicking the sibling span's coordinates if not.
- CHANGE_LINK_LOCATOR: screens/choose-what-to-move/UserStorageSummaryCard.tsx, a DDSLink
  labelled t('Buttons_Change') = "Change" (one per drive row; this matches the first).
- CANCEL_LINK_LOCATOR: ChooseWhatToMoveStage.tsx passes onAction to StagePanel with no
  actionLabel, so components/stage/StagePanelHeader.tsx renders a DDSLink labelled its
  default t('Buttons_Cancel') = "Cancel" (plus an aria-hidden close-x icon). A link, not
  a Button, hence //* rather than //Button.
"""

LET_ME_CHOOSE_LINK_LOCATOR = ("xpath", '//*[@Name="Let me choose what to transfer"]')
GO_BACK_LINK_LOCATOR = ("xpath", '//*[@Name="Go back"]')
SELECT_ALL_CHECKBOX_LOCATOR = ("xpath", "(//CheckBox)[1]")
CHANGE_LINK_LOCATOR = ("xpath", '//*[@Name="Change"]')
CANCEL_LINK_LOCATOR = ("xpath", '//*[@Name="Cancel"]')
