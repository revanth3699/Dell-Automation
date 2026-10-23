// Screen-catalog scenario registry — the single source of truth for the dev-only navigation harness
// (catalog.html / src/catalog/*). Every ScreenId, OverlayId and close-prompt step in bridge/contract.ts has
// at least one entry, and the ARRAY ORDER IS THE USER JOURNEY (onboarding → prerequisites → pairing →
// compatibility → selection → migrating → results → global popups), with each popup placed directly after
// the screen it genuinely appears over. Automation iterates the manifest in this order.
//
// Where the text comes from — this matters for text validation:
//   • Anything the native view models take from Resources.resx is resolved here through res(key), the same
//     key the C# reads, so it is the authoritative copy and follows locale (&locale=de).
//   • Strings the C# hard-codes (e.g. "Starting the move…", ConnectionLost's body, the wrong-code message)
//     are copied verbatim with the C# location in a comment — there is no resx key to resolve them from.
//   • Values that only exist at run time (profile/device names, sizes, percentages, drive letters, the
//     settings-group names the old PC's engine reports) are SAMPLE data. They exercise layout and wrapping;
//     they are not authoritative copy. Marked "sample" below.
//
// Every popup scenario has two views (see hasPopup): the default shows the popup; `popups=hidden` renders the
// same screen with the popup layer removed so the background text can be validated unobscured.
// All states are lazy (() => state) because res() needs i18n's language set first (main.tsx does that).
import type {
  ChooseWhatToMoveNodeState,
  ChooseWhatToMoveScreenState,
  ChromeState,
  CloseApplicationsScreenState,
  CloseStep,
  CompleteScreenState,
  ConnectOldPcScreenState,
  EnterCodeScreenState,
  FailureScreenState,
  MigratingScreenState,
  OverlayId,
  PrecheckScreenState,
  ReportTreeNodeState,
  ResultsSummaryScreenState,
  ScreenId,
  SignInScreenState,
  SkippedFilesScreenState,
  SkippedItemNodeState,
  SummaryTileState,
  WelcomeScreenState,
} from '@app/bridge/contract'
import { res } from './res'
import { click, clickKey, focusEl, typeInto, type Step } from './steps'

export type ThemeName = 'light' | 'dark'

export type Phase =
  | 'onboarding'
  | 'prerequisites'
  | 'pairing'
  | 'compatibility'
  | 'selection'
  | 'migrating'
  | 'results'
  | 'global'

export const PHASES: { id: Phase; label: string }[] = [
  { id: 'onboarding', label: '1 · Onboarding & reminders' },
  { id: 'prerequisites', label: '2 · Prerequisites check' },
  { id: 'pairing', label: '3 · Pairing with the old PC' },
  { id: 'compatibility', label: '4 · Compatibility' },
  { id: 'selection', label: '5 · Choose what to move' },
  { id: 'migrating', label: '6 · Migrating' },
  { id: 'results', label: '7 · Results & finish' },
  { id: 'global', label: '8 · App-wide popups' },
]

/** What kind of surface a scenario is — the index groups by this, so there is no ambiguity about what is
 *  being looked at. 'screen' is a plain screen state; 'popup' is a modal over a screen; 'dropdown' is a
 *  dropdown list held open; 'selection' is a multi-select / choice state (checkbox trees, radio options);
 *  'input' is a text/code/rating entry state. Popups are derived (see categoryOf); the rest are explicit. */
export type Category = 'screen' | 'popup' | 'dropdown' | 'selection' | 'input' | 'tooltip'

export const CATEGORIES: { id: Category; label: string }[] = [
  { id: 'screen', label: 'Screen states' },
  { id: 'popup', label: 'Popups' },
  { id: 'dropdown', label: 'Dropdowns open' },
  { id: 'selection', label: 'Selections (multi-select & choices)' },
  { id: 'input', label: 'Inputs (code, rating, comment)' },
  { id: 'tooltip', label: 'Tooltips (hover text held open)' },
]

interface ScenarioBase {
  phase: Phase
  variant: string
  title: string
  /** Overrides the derived category (dropdown / selection / input are never derivable). */
  category?: Exclude<Category, 'screen' | 'popup'>
  /** Partial chrome (header) override merged over defaultChrome. */
  chrome?: Partial<ChromeState>
  /** UI actions run after first paint to reach a React-local surface. popup:true steps are skipped in the
   *  background-only view. */
  steps?: Step[]
}

/** A full screen, pushed via screen.navigate + screen.state. */
export interface ScreenScenario extends ScenarioBase {
  kind: 'screen'
  screen: ScreenId
  state: () => unknown
  /** Set when the screen's own state drives a popup (e.g. showNoDeviceFoundModal): the same screen with that
   *  popup switched off, used for the background-only view. */
  popupOffState?: () => unknown
}

/** An overlay on top of `base`, pushed via overlay.navigate + overlay.state after the base screen. */
export interface OverlayScenario extends ScenarioBase {
  kind: 'overlay'
  overlay: OverlayId
  base: ScreenId
  baseState: () => unknown
  state: () => unknown
}

/** An app-global close prompt (app.closeConfirm) over `base`. */
export interface ClosePromptScenario extends ScenarioBase {
  kind: 'closePrompt'
  step: Exclude<CloseStep, 'none'>
  base: ScreenId
  baseState: () => unknown
}

export type Scenario = ScreenScenario | OverlayScenario | ClosePromptScenario

/** True when the scenario has a popup that the background-only view removes. */
export function hasPopup(s: Scenario): boolean {
  if (s.kind !== 'screen') {
    return true
  }
  return s.popupOffState !== undefined || (s.steps ?? []).some((step) => step.popup === true)
}

/** The category the index files a scenario under. */
export function categoryOf(s: Scenario): Category {
  if (s.category) {
    return s.category
  }
  return hasPopup(s) ? 'popup' : 'screen'
}

// Human names for the host screens, as the index shows them.
export const SCREEN_LABELS: Record<ScreenId, string> = {
  welcome: 'Welcome',
  welcomeDeferral: 'Remind me later (picker)',
  welcomeDeferralError: 'Remind me later (error)',
  deferralSuccess: 'Reminder set',
  migrateReminder: 'Migrate reminder (picker)',
  migrateReminderSet: 'Migrate reminder (confirmation)',
  checkPrerequisites: 'Check prerequisites',
  connectOldPc: 'Connect old PC',
  enterCode: 'Enter code',
  readyToMove: 'Ready to move',
  chooseWhatToMove: 'Choose what to move',
  migrating: 'Migrating',
  resultsSummary: 'Results summary',
  complete: 'Complete (report)',
  skippedFiles: 'Skipped files',
  migrationDone: 'Migration done',
  learnAboutErase: 'Learn about erase',
}

/** The screen a scenario belongs to: itself for a screen, the screen it sits over for a popup. */
export function hostScreen(s: Scenario): ScreenId {
  return s.kind === 'screen' ? s.screen : s.base
}

/** Index group within a phase: app-wide popups have no single host, so they share one group. */
export function groupOf(s: Scenario): { key: string; label: string } {
  if (s.phase === 'global') {
    return { key: 'global', label: 'Shown over whichever screen is current' }
  }
  const host = hostScreen(s)
  return { key: host, label: SCREEN_LABELS[host] }
}

/** Short row label: a screen state drops its screen name (the group heading already says it). */
export function labelOf(s: Scenario): string {
  if (s.kind === 'screen') {
    const at = s.title.indexOf(' — ')
    return at >= 0 ? s.title.slice(at + 3) : s.title
  }
  return s.title
}

// ── Chrome ───────────────────────────────────────────────────────────────────
// A populated, signed-in, connected header (sample values) so chrome renders fully by default.
export const defaultChrome: ChromeState = {
  isSignedIn: true,
  isNetworkConnected: true,
  networkName: 'HomeWiFi',
  isWifi: true,
  wifiStrength: 80,
  acPluggedIn: true,
  batteryPercent: 85,
  isMaximized: true,
}

// ── Sample run-time data (not authoritative copy) ────────────────────────────
const sampleUser = 'Alex'
const sampleProfile = 'Alex Morgan'
const sampleDevice = 'Dell XPS 15'

// StorageSummary.FormatEstimate / FormatMinutes / FormatHours (StorageSummary.cs) — the same resx formats, so an
// estimate reads exactly as the app words it: "14 minutes", "1 hour and 5 minutes", "less than a minute".
const minutesText = (n: number): string => res(n === 1 ? 'Duration_Minute' : 'Duration_Minutes', n)
const hoursText = (n: number): string => res(n === 1 ? 'Duration_Hour' : 'Duration_Hours', n)
const duration = (totalMinutes: number): string => {
  if (totalMinutes < 1) {
    return res('Duration_LessThanAMinute')
  }
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (hours === 0) {
    return minutesText(minutes)
  }
  return minutes === 0 ? hoursText(hours) : res('Duration_Join', hoursText(hours), minutesText(minutes))
}

// ── Screen states, reused as scenario states and as popup bases ──────────────
const welcome = (o: Partial<WelcomeScreenState> = {}): WelcomeScreenState => ({
  isSignedIn: false, userName: '', isLaunching: false, isFirstLaunch: true, isWithoutMigrate: false, ...o,
})
// WelcomePageViewModel.cs:319 sets IsLaunching and nothing resets it if the engine then fails to start.
const welcomeLaunching = () => welcome({ isSignedIn: true, userName: sampleUser, isLaunching: true })

const checkPrereq = (o: { isLaunching?: boolean; isChecking?: boolean; isReady?: boolean; userName?: string }) => ({
  isLaunching: false, isChecking: false, isReady: false, userName: sampleUser, ...o,
})

const connectOldPc = (o: Partial<ConnectOldPcScreenState> = {}): ConnectOldPcScreenState => ({
  statusMessage: '', showNoDeviceFoundModal: false, ...o,
})

const enterCode = (o: Partial<EnterCodeScreenState> = {}): EnterCodeScreenState => ({
  enteredCode: '', codeLength: 6, canLink: false, isSuccess: false, isLinking: false, isLocked: false,
  showNoDeviceFoundModal: false, statusMessage: '', ...o,
})

// ReadyToMovePageViewModel.cs:127-434 — the hard-coded status line, in the order the VM sets it.
const readyToMove = (statusMessage = 'Gathering what can move from your old PC…') => ({ statusMessage })

function treeNode(o: Partial<ChooseWhatToMoveNodeState> & { nodeId: string; name: string }): ChooseWhatToMoveNodeState {
  return {
    path: '', isSelected: true, isSelectable: true, isCategory: false, isLoading: false, isPlaceholder: false,
    canExpand: false, childrenLoaded: true, sizeDisplay: '', pathTooltip: null, children: [], ...o,
  }
}

// SelectionNode.AddExpansionPlaceholder — what native pushes under a not-yet-expanded drive/folder (React skips it).
const placeholder = (parentId: string): ChooseWhatToMoveNodeState =>
  treeNode({ nodeId: `${parentId}.0`, name: 'Loading…', isPlaceholder: true, isSelectable: false, canExpand: false, childrenLoaded: false })

// Shape mirrors SelectionTreeBuilder.BuildTree: Settings category first, then the PC (files) category; both
// start collapsed on the React side. Category labels use the real resx formats; the settings groups and
// folder names below are sample data (the old PC's engine supplies them at run time).
function selectionTree(o: { partial?: boolean } = {}): ChooseWhatToMoveNodeState[] {
  const partial = o.partial === true
  return [
    treeNode({
      nodeId: '0', name: res('ChooseWhatToMove_SettingsCategoryFormat', sampleProfile), isCategory: true, canExpand: true,
      isSelected: partial ? null : true, sizeDisplay: '',
      children: [
        treeNode({
          nodeId: '0.0', name: 'Desktop and personalization', canExpand: true, isSelected: partial ? null : true,
          children: [
            treeNode({ nodeId: '0.0.0', name: 'Wallpaper', isSelected: true }),
            treeNode({ nodeId: '0.0.1', name: 'Taskbar layout', isSelected: partial ? false : true }),
          ],
        }),
        treeNode({
          nodeId: '0.1', name: 'Browser bookmarks', canExpand: true, isSelected: true,
          children: [
            treeNode({ nodeId: '0.1.0', name: 'Chrome bookmarks', isSelected: true }),
            treeNode({ nodeId: '0.1.1', name: 'Edge favorites', isSelected: true }),
          ],
        }),
        treeNode({ nodeId: '0.2', name: 'Wi-Fi networks', isSelected: true }),
      ],
    }),
    // Category rows never carry a size (SelectionNode.SizeInBytes is only set from a folder-tree response); a drive
    // or folder not yet expanded holds exactly one placeholder child, which React does not draw (SelectionTreeBuilder
    // AddExpansionPlaceholder). Drive/folder/file rows carry their path as a hover title (SelectionNode.PathTooltip).
    treeNode({
      nodeId: '1', name: res('ChooseWhatToMove_PcCategoryFormat', sampleProfile), isCategory: true, canExpand: true,
      isSelected: partial ? null : true, sizeDisplay: '',
      children: [
        treeNode({
          nodeId: '1.0', name: res('ChooseWhatToMove_SystemDriveLabelFormat', 'C:'), path: 'C:\\', pathTooltip: 'C:\\', canExpand: true,
          isSelected: partial ? null : true, sizeDisplay: '24.5 GB',
          children: [
            treeNode({ nodeId: '1.0.0', name: 'Documents', path: 'C:\\Users\\Alex\\Documents\\', pathTooltip: 'C:\\Users\\Alex\\Documents\\', canExpand: true, isSelected: true, sizeDisplay: '12.1 GB', childrenLoaded: false, children: [placeholder('1.0.0')] }),
            treeNode({ nodeId: '1.0.1', name: 'Pictures', path: 'C:\\Users\\Alex\\Pictures\\', pathTooltip: 'C:\\Users\\Alex\\Pictures\\', canExpand: true, isSelected: partial ? false : true, sizeDisplay: '9.8 GB', childrenLoaded: false, children: [placeholder('1.0.1')] }),
            treeNode({ nodeId: '1.0.2', name: 'notes.txt', path: 'C:\\notes.txt', pathTooltip: 'C:\\notes.txt', isSelected: true, sizeDisplay: '4 KB' }),
          ],
        }),
        treeNode({ nodeId: '1.1', name: 'D:', path: 'D:\\', pathTooltip: 'D:\\', canExpand: true, isSelected: partial ? false : true, childrenLoaded: false, children: [placeholder('1.1')] }),
      ],
    }),
  ]
}

// DriveStorageSummary.cs:82 — the resx format is given the drive letter with its colon trimmed ("C").
const storageHeading = (driveLetter: string): string =>
  res('ChooseWhatToMove_StorageSpaceLabel', driveLetter.replace(/:+$/, ''))

function storageRow(o: Partial<ChooseWhatToMoveScreenState['driveStorageRows'][number]> = {}) {
  return {
    driveLetter: 'C:', headingText: storageHeading('C:'), currentSizeText: '512 GB',
    neededSizeText: '28 GB', remainingSizeText: '484 GB', currentFraction: 0.5, neededFraction: 0.3, remainingFraction: 0.2,
    fitsOnDestination: true, shortfallText: '', ...o,
  }
}

// DriveMappingOptionsBuilder shape — sample drives/destinations.
const driveMappingRows = () => [
  { driveId: 'C:', label: res('DriveMapping_TransferFromFormat', 'C'), options: ['C:\\', 'D:\\Migration_C_Drive'], selectedOption: 'C:\\', selected: true },
  { driveId: 'D:', label: res('DriveMapping_TransferFromFormat', 'D'), options: ['C:\\Migration_D_Drive', 'D:\\'], selectedOption: 'D:\\', selected: true },
]

// With four drives on this PC every row offers four destinations: the bare root for the same letter, otherwise a
// Migration_<letter>_Drive folder on each other drive (DriveMappingOptionsBuilder; CdmConfiguration MigrationDirectory).
const threeDriveRows = () => ['C', 'D', 'E'].map((letter) => ({
  driveId: `${letter}:`, label: res('DriveMapping_TransferFromFormat', letter),
  options: ['C', 'D', 'E', 'F'].map((target) => (target === letter ? `${target}:\\` : `${target}:\\Migration_${letter}_Drive`)),
  selectedOption: `${letter}:\\`, selected: true,
}))

const choose = (o: Partial<ChooseWhatToMoveScreenState> = {}): ChooseWhatToMoveScreenState => ({
  profileName: sampleProfile, deviceModel: sampleDevice, isLoading: false, loadingCaption: '', neededSizeText: '28 GB',
  fitsOnDestination: true, statusMessage: '', needsToCloseApplications: false, estimateText: duration(14),
  moveEverything: true, showTree: false, allSelectedState: true, canMigrate: true, nodes: [],
  driveStorageRows: [storageRow()], isDriveMappingModalOpen: false,
  driveMappingHeading: res('DriveMapping_HeadingMultiple'), driveMappingRows: [], isRescanning: false,
  isRecalculating: false, isApplyingDriveMapping: false, canApplyDriveMapping: false, ...o,
})

const selectFiles = (o: Partial<ChooseWhatToMoveScreenState> = {}) =>
  choose({ moveEverything: false, showTree: true, nodes: selectionTree(), ...o })

const migrating = (o: Partial<MigratingScreenState> = {}): MigratingScreenState => ({
  filePercent: 45, settingsPercent: 10, hasSelectedFiles: true, hasSelectedSettings: true,
  currentTask: 'Copying Documents', transferredText: '12 GB of 28 GB', remainingText: duration(14),
  transferSpeedText: '15 MB/s', statusMessage: '', isMigrating: true, hasSkippedItems: false,
  settingsHasSkipped: false, canCancel: true, ...o,
})

const migratingDone = (o: Partial<MigratingScreenState> = {}) =>
  migrating({ filePercent: 100, settingsPercent: 100, currentTask: '', transferredText: '', remainingText: '',
    transferSpeedText: '', isMigrating: false, canCancel: false, ...o })

// MigrationSummaryTiles.Build — always six tiles, in this order (ResultsSummaryScreenAdapter.ProjectTiles passes them
// all through). Values are sample run-time data, formatted the way the C# formats them: counts as plain integers,
// sizes through StorageSummary.FormatBytes, elapsed time as hh:mm:ss (MigrationReportView.cs).
const summaryTiles = (o: { files?: string; data?: string; notMigrated?: string; settings?: string; elapsed?: string; existing?: string } = {}): SummaryTileState[] => [
  { icon: 'FilesCopied', value: o.files ?? '1284', label: res('ResultsSummary_LabelFilesCopied') },
  { icon: 'DataTransferred', value: o.data ?? '12.4 GB', label: res('ResultsSummary_LabelDataTransferred') },
  { icon: 'NotMigrated', value: o.notMigrated ?? '0', label: res('ResultsSummary_LabelItemsNotTransferred') },
  { icon: 'SettingsCopied', value: o.settings ?? '18', label: res('ResultsSummary_LabelSettingsCopied') },
  { icon: 'ElapsedTime', value: o.elapsed ?? '00:14:05', label: res('ResultsSummary_LabelElapsedTime') },
  { icon: 'AlreadyExisting', value: o.existing ?? '0 B', label: res('ResultsSummary_LabelDuplicatesSkipped') },
]
// MigrationSummaryTiles.BuildUnavailable — every value is an em dash.
const unavailableTiles = (): SummaryTileState[] =>
  summaryTiles({ files: '—', data: '—', notMigrated: '—', settings: '—', elapsed: '—', existing: '—' })
// MigrationReportView.cs formats the date as 'MMMM dd, yyyy, at h:mm tt'.
const ranText = (): string => res('ResultsSummary_MigrationRanText', 'October 23, 2026, at 3:45 PM')

// ResultsSummaryPageViewModel.Apply sets statusMessage, but React never renders it; kept as the VM sets it.
const results = (o: Partial<ResultsSummaryScreenState> = {}): ResultsSummaryScreenState => ({
  isLoading: false, wasCancelled: false, isReady: true, headlineText: res('ResultsSummary_Title'),
  hasSkippedItems: false, statusMessage: 'Your files and settings have moved.', migrationRanText: ranText(),
  skippedSubtextText: '', tiles: summaryTiles(),
  rebootRequired: false, rebootReasonText: '', canFinish: true, ...o,
})

// ReportTreeNode.DisplayText is 'Name (Count)'. The Files root is flat — a count and a size, no children
// (MigrationSummaryTiles.BuildFilesCopiedNode). The Settings root holds 'Group (count)' rows, each with the setting
// names (DetailedReportTreeBuilder.BuildSettingsNode). Names and counts are sample data.
const filesRoot = (key: string, count: number, size = ''): ReportTreeNodeState =>
  ({ displayText: `${res(key)} (${count})`, isRoot: true, sizeDisplay: size, children: [] })
const settingsRoot = (key: string, withGroups = true): ReportTreeNodeState => ({
  displayText: `${res(key)} (${withGroups ? 2 : 0})`, isRoot: true,
  children: withGroups ? [{ displayText: 'Desktop and personalization (2)', isRoot: false, children: [
    { displayText: 'Wallpaper', isRoot: false, children: [] }, { displayText: 'Taskbar layout', isRoot: false, children: [] },
  ] }] : [],
})
const completeReport = (): ReportTreeNodeState[] => [filesRoot('Complete_FilesTransferred', 1284, '12.4 GB'), settingsRoot('Complete_SettingsTransferred')]
const skippedReadOnly = (): ReportTreeNodeState[] => [filesRoot('SkippedFiles_FilesCopied', 1284, '12.4 GB'), settingsRoot('SkippedFiles_SettingsCopied')]

const complete = (): CompleteScreenState => ({
  profileName: sampleProfile, deviceModel: sampleDevice, nodes: completeReport(), canOpenPdf: true, statusMessage: '',
})

const skippedLeaf = (o: Partial<SkippedItemNodeState> & { nodeId: string; displayText: string }): SkippedItemNodeState => ({
  sizeDisplay: '', reason: '', isLeaf: true, hasReason: true, isRoot: false, isChecked: true, canExpand: false,
  childrenLoaded: true, isLoading: false, children: [], ...o,
})

// SkippedItemsTreeBuilder shape: a 'Files not copied (N)' root (hard-coded in C#, not resx; no checkbox, open by
// default) holding one row per drive (named by the engine's RootDirectory, collapsed), then the skipped files; and a
// 'Settings not copied (N)' root with group rows and setting leaves. A leaf's reason is the SkipReason_<code> resx
// string, shown only in a hover tooltip. File names, sizes and groups are sample data.
const skippedTree = (o: { leafChecked?: boolean[]; withDirectory?: boolean; directoryLoading?: boolean } = {}): SkippedItemNodeState[] => {
  const checked = o.leafChecked ?? [true, true]
  const fileLeaves = [
    skippedLeaf({ nodeId: '0.0.0', displayText: 'budget.xlsx', sizeDisplay: '1 MB', reason: res('SkipReason_2953'), isChecked: checked[0] }),
    skippedLeaf({ nodeId: '0.0.1', displayText: 'draft.docx', sizeDisplay: '200 KB', reason: res('SkipReason_2954'), isChecked: checked[1] }),
    ...(o.withDirectory === false ? [] : [skippedLeaf({ nodeId: '0.0.2', displayText: 'Archive', reason: res('SkipReason_2956'), canExpand: true, childrenLoaded: false, isLoading: o.directoryLoading === true, isChecked: true })]),
  ]
  const groupState: boolean | null = fileLeaves.every((l) => l.isChecked === true) ? true : fileLeaves.every((l) => l.isChecked === false) ? false : null
  return [
    skippedLeaf({ nodeId: '0', displayText: `Files not copied (${fileLeaves.length})`, isLeaf: false, hasReason: false, isRoot: true, isChecked: groupState, children: [
      skippedLeaf({ nodeId: '0.0', displayText: 'C:\\', isLeaf: false, hasReason: false, isChecked: groupState, children: fileLeaves }),
    ] }),
    skippedLeaf({ nodeId: '1', displayText: 'Settings not copied (1)', isLeaf: false, hasReason: false, isRoot: true, children: [
      skippedLeaf({ nodeId: '1.0', displayText: 'Desktop and personalization', isLeaf: false, hasReason: false, children: [
        skippedLeaf({ nodeId: '1.0.0', displayText: 'Wallpaper', reason: res('SkipReason_2414') }),
      ] }),
    ] }),
  ]
}

// SkippedFilesPageViewModel.RecalculateEstimatedTime: 'Estimated time: {duration} ({size} selected)'.
const skipped = (o: Partial<SkippedFilesScreenState> = {}): SkippedFilesScreenState => ({
  nodes: skippedReadOnly(), skippedNodes: skippedTree(), canAct: true, hasSelection: true, retryVisible: true, networkLost: false,
  profileName: sampleProfile, deviceModel: sampleDevice, estimatedTimeText: 'Estimated time: less than a minute (1.2 MB selected)',
  statusMessage: '', ...o,
})

const precheck = (title: string, body: string): PrecheckScreenState => ({ title, body, imageUrl: null })

// ConnectionLostScreenAdapter.cs:38-39 — hard-coded in C#, not in resx.
const connectionLost = () => precheck('Connection lost',
  'We lost the connection to your other PC. Make sure both PCs are on the same network, then try again.')

const failure = (o: Partial<FailureScreenState> = {}): FailureScreenState => ({ message: '', dismissible: false, ...o })

const signIn = (o: Partial<SignInScreenState> = {}): SignInScreenState => ({
  isSigningIn: false, isOpeningBrowser: false, isLaunching: false, errorMessage: undefined, ...o,
})

const closeApps = (o: Partial<CloseApplicationsScreenState> = {}): CloseApplicationsScreenState => ({
  runningApplications: ['Chrome', 'Slack'], primaryButtonText: 'Close it now', statusMessage: '', canClose: true,
  hasFailedAttempt: false, ...o,
})

// MigrateReminderOptions.cs:17-20 — the four durations, with one marked selected.
const reminderPicker = (selectedToken: string, errorMessage: string | null = null) => ({
  options: [
    { intervalToken: '1 h', label: 'In an hour' },
    { intervalToken: '6 h', label: 'In 6 hours' },
    { intervalToken: '1 d', label: 'Tomorrow' },
    { intervalToken: '1 w', label: 'Next week' },
  ].map((option) => ({ ...option, isSelected: option.intervalToken === selectedToken })),
  errorMessage,
})

// FeedbackModal's StarRating renders two buttons per star (left half, then whole), in order: index 2n+1 is the
// whole-star button of star n+1, and 2n its half-star button — so 7 is a 4-star rating, 6 is 3.5 stars.
const star = (index: number) => click('[role="radiogroup"] button[aria-pressed]', { nth: index, popup: true })
const openFeedback = clickKey('MigrationDone_TellUsHowWeDid', { popup: true })
const comment = (text: string) => typeInto('#feedback-comment', text, { popup: true })

// The DDS dropdown opens on a click on its input (DriveMappingModal.tsx remarks); nth picks the row.
const openDriveDropdown = (row: number) => click('dialog .dds__dropdown input', { nth: row, popup: true })

// ── The registry (in journey order) ──────────────────────────────────────────

// One entry per DISTINCT SkipReason_<code> text (codes that share their wording share an entry, the codes are in its title): a skipped file's (or setting's) reason is shown only in a tooltip on its
// info icon, which DDS opens on focus. The list mirrors the keys in Resources.resx (a test compares it with
// screens.json). Codes 2946-2956 are the file reasons the engine emits (SkippedEntryErrorCode); the rest are
// setting reasons. 2203, 2207, 2420, 2438 and 2952 have no proven emitter — they exist in the resx, so they are
// shown, but see scripts/catalog-coverage-exceptions.json.
export const SKIP_REASON_GROUPS: number[][] = [
  [2201, 2202, 2203, 2204, 2205],
  [2207],
  [2406, 2433],
  [2407, 2434],
  [2408, 2435],
  [2409, 2436],
  [2410, 2437],
  [2411],
  [2412, 2453],
  [2413, 2440],
  [2414],
  [2415, 2442],
  [2416, 2443],
  [2417],
  [2418, 2445],
  [2419],
  [2420, 2432],
  [2421, 2447],
  [2422, 2448],
  [2423, 2449],
  [2424, 2450],
  [2425, 2451],
  [2426, 2452],
  [2427],
  [2428],
  [2429],
  [2430],
  [2431],
  [2438],
  [2439],
  [2441],
  [2444],
  [2446],
  [2454],
  [2455, 2456],
  [2508],
  [2509],
  [2510],
  [2511],
  [2946, 2948, 2951],
  [2947, 2949, 2950],
  [2952],
  [2953, 2954],
  [2955],
  [2956],
  [2978],
]
export const SKIP_REASON_CODES: number[] = SKIP_REASON_GROUPS.flat()

const isFileReason = (code: number): boolean => code >= 2946 && code <= 2956

const reasonState = (code: number): SkippedFilesScreenState => skipped({
  nodes: [filesRoot('SkippedFiles_FilesCopied', 1284, '12.4 GB'), settingsRoot('SkippedFiles_SettingsCopied', false)],
  skippedNodes: isFileReason(code)
    ? [skippedLeaf({ nodeId: '0', displayText: 'Files not copied (1)', isLeaf: false, hasReason: false, isRoot: true, children: [
        skippedLeaf({ nodeId: '0.0', displayText: 'C:\\', isLeaf: false, hasReason: false, children: [
          skippedLeaf({ nodeId: '0.0.0', displayText: 'budget.xlsx', sizeDisplay: '1 MB', reason: res(`SkipReason_${code}`) }),
        ] }),
      ] })]
    : [skippedLeaf({ nodeId: '0', displayText: 'Settings not copied (1)', isLeaf: false, hasReason: false, isRoot: true, children: [
        skippedLeaf({ nodeId: '0.0', displayText: 'Desktop and personalization', isLeaf: false, hasReason: false, children: [
          skippedLeaf({ nodeId: '0.0.0', displayText: 'Wallpaper', reason: res(`SkipReason_${code}`) }),
        ] }),
      ] })],
})

// The root is open by default, so the group row is expander [1]; focusing the leaf's info icon opens its tooltip.
export const skipReasonScenarios: Scenario[] = SKIP_REASON_GROUPS.map((codes): Scenario => ({
  kind: 'screen', phase: 'results', screen: 'skippedFiles', category: 'tooltip',
  variant: `reason${codes[0]}`, title: `Skip reason ${codes.join(' · ')} (hover text)`,
  state: () => reasonState(codes[0]),
  steps: [click('button[class*="expander"]', { nth: 1 }), focusEl('span[tabindex="0"]', { nth: 0 })],
}))

export const scenarios: Scenario[] = [
  // 1 · Onboarding & reminders ────────────────────────────────────────────────
  { kind: 'screen', phase: 'onboarding', screen: 'welcome', variant: 'signedOut', title: 'Welcome — not signed in', chrome: { isSignedIn: false }, state: () => welcome() },
  { kind: 'screen', phase: 'onboarding', screen: 'welcome', variant: 'signedIn', title: 'Welcome — signed in (welcome back)', state: () => welcome({ isSignedIn: true, userName: sampleUser }) },
  { kind: 'screen', phase: 'onboarding', screen: 'welcome', variant: 'launching', title: 'Welcome — starting up after sign-in', state: () => welcome({ isSignedIn: true, userName: sampleUser, isLaunching: true }) },
  { kind: 'screen', phase: 'onboarding', screen: 'welcome', variant: 'noMigrateSignedOut', title: 'Welcome — account only, not signed in', chrome: { isSignedIn: false }, state: () => welcome({ isWithoutMigrate: true }) },
  { kind: 'screen', phase: 'onboarding', screen: 'welcome', variant: 'noMigrateSignedIn', title: 'Welcome — account only, signed in', state: () => welcome({ isWithoutMigrate: true, isSignedIn: true, userName: sampleUser }) },

  { kind: 'overlay', phase: 'onboarding', overlay: 'signIn', variant: 'idle', title: 'Sign in — idle', chrome: { isSignedIn: false }, base: 'welcome', baseState: () => welcome(), state: () => signIn() },
  { kind: 'overlay', phase: 'onboarding', overlay: 'signIn', variant: 'opening', title: 'Sign in — opening the browser (Retry off)', chrome: { isSignedIn: false }, base: 'welcome', baseState: () => welcome(), state: () => signIn({ isSigningIn: true, isOpeningBrowser: true }) },
  { kind: 'overlay', phase: 'onboarding', overlay: 'signIn', variant: 'waiting', title: 'Sign in — waiting for browser', chrome: { isSignedIn: false }, base: 'welcome', baseState: () => welcome(), state: () => signIn({ isSigningIn: true }) },
  { kind: 'overlay', phase: 'onboarding', overlay: 'signIn', variant: 'launching', title: 'Sign in — starting the assistant', chrome: { isSignedIn: false }, base: 'welcome', baseState: () => welcome(), state: () => signIn({ isSigningIn: true, isLaunching: true }) },
  { kind: 'overlay', phase: 'onboarding', overlay: 'signIn', variant: 'error', title: 'Sign in — error', chrome: { isSignedIn: false }, base: 'welcome', baseState: () => welcome(), state: () => signIn({ errorMessage: res('SignIn_ErrorBody') }) },

  { kind: 'screen', phase: 'onboarding', screen: 'welcomeDeferral', variant: 'picker', title: 'Remind me later — picker', state: () => ({}) },
  { kind: 'screen', phase: 'onboarding', screen: 'welcomeDeferralError', variant: 'error', title: 'Remind me later — could not set reminder', state: () => ({ errorMessage: "We couldn't set that reminder. Please try again." }) },
  { kind: 'screen', phase: 'onboarding', screen: 'deferralSuccess', variant: 'tonight', title: 'Reminder set — tonight', state: () => ({ reminderChoice: 'tonight' }) },
  { kind: 'screen', phase: 'onboarding', screen: 'deferralSuccess', variant: 'tomorrow', title: 'Reminder set — tomorrow', state: () => ({ reminderChoice: 'tomorrow' }) },
  { kind: 'screen', phase: 'onboarding', screen: 'deferralSuccess', variant: 'nextWeek', title: 'Reminder set — next week', state: () => ({ reminderChoice: 'nextWeek' }) },

  // MigrateReminderOptions.cs:17-20,33 — labels and headline are hard-coded in C#.
  { kind: 'screen', phase: 'onboarding', screen: 'migrateReminder', variant: 'default', title: 'Migrate reminder — “In an hour” selected (default)', state: () => reminderPicker('1 h') },
  { kind: 'screen', phase: 'onboarding', screen: 'migrateReminder', variant: 'error', title: 'Migrate reminder — could not set reminder', state: () => reminderPicker('1 h', "We couldn't set that reminder. Please try again.") },
  { kind: 'screen', phase: 'onboarding', screen: 'migrateReminderSet', variant: 'default', title: 'Migrate reminder — confirmation', state: () => ({ headlineText: "Okay, we'll remind you again in an hour." }) },
  { kind: 'screen', phase: 'onboarding', screen: 'migrateReminderSet', variant: 'sixHours', title: 'Migrate reminder — confirmation (6 hours)', state: () => ({ headlineText: "Okay, we'll remind you again in 6 hours." }) },
  { kind: 'screen', phase: 'onboarding', screen: 'migrateReminderSet', variant: 'tomorrow', title: 'Migrate reminder — confirmation (tomorrow)', state: () => ({ headlineText: "Okay, we'll remind you again tomorrow." }) },
  { kind: 'screen', phase: 'onboarding', screen: 'migrateReminderSet', variant: 'nextWeek', title: 'Migrate reminder — confirmation (next week)', state: () => ({ headlineText: "Okay, we'll remind you again next week." }) },

  // 2 · Prerequisites check ───────────────────────────────────────────────────
  { kind: 'screen', phase: 'prerequisites', screen: 'checkPrerequisites', variant: 'checking', title: 'Check prerequisites — checking (named)', state: () => checkPrereq({ isChecking: true }) },
  { kind: 'screen', phase: 'prerequisites', screen: 'checkPrerequisites', variant: 'checkingNoName', title: 'Check prerequisites — checking (no name)', state: () => checkPrereq({ isChecking: true, userName: '' }) },

  { kind: 'overlay', phase: 'prerequisites', overlay: 'trustNetwork', variant: 'idle', title: 'Trust network — idle', base: 'checkPrerequisites', baseState: () => checkPrereq({ isChecking: true }), state: () => ({ canTrust: true, statusMessage: '' }) },
  // TrustNetworkPageViewModel.cs:119,186 — hard-coded status lines. (:233 'still public' and :178 are cleared by Initialize() before the popup shows, so no state carries them.)
  { kind: 'overlay', phase: 'prerequisites', overlay: 'trustNetwork', variant: 'trusting', title: 'Trust network — trusting', base: 'checkPrerequisites', baseState: () => checkPrereq({ isChecking: true }), state: () => ({ canTrust: false, statusMessage: 'Trusting this network…' }) },
  { kind: 'overlay', phase: 'prerequisites', overlay: 'trustNetwork', variant: 'failed', title: 'Trust network — could not trust', base: 'checkPrerequisites', baseState: () => checkPrereq({ isChecking: true }), state: () => ({ canTrust: true, statusMessage: "We couldn't trust this network. Please try again." }) },

  { kind: 'overlay', phase: 'prerequisites', overlay: 'notAdmin', variant: 'default', title: 'Not an administrator', base: 'checkPrerequisites', baseState: () => checkPrereq({ isChecking: true }), state: () => precheck(res('NotAdmin_Title'), res('NotAdmin_Body')) },
  { kind: 'overlay', phase: 'prerequisites', overlay: 'osNotSupported', variant: 'default', title: 'Windows version not supported', base: 'checkPrerequisites', baseState: () => checkPrereq({ isChecking: true }), state: () => precheck(res('OsNotSupported_Title'), res('OsNotSupported_Body')) },
  { kind: 'overlay', phase: 'prerequisites', overlay: 'localeNotSupported', variant: 'default', title: 'Language not supported', base: 'checkPrerequisites', baseState: () => checkPrereq({ isChecking: true }), state: () => precheck(res('LocaleNotSupported_Title'), res('LocaleNotSupported_Body')) },
  { kind: 'overlay', phase: 'prerequisites', overlay: 'batteryCritical', variant: 'default', title: 'Battery too low', base: 'checkPrerequisites', baseState: () => checkPrereq({ isChecking: true }), state: () => precheck(res('BatteryCritical_Title'), res('BatteryCritical_Body')), chrome: { acPluggedIn: false, batteryPercent: 4 } },
  { kind: 'overlay', phase: 'prerequisites', overlay: 'noNetwork', variant: 'thisPcPrecheck', title: 'No network — this PC (precheck)', base: 'checkPrerequisites', baseState: () => checkPrereq({ isChecking: true }), state: () => precheck(res('NoNetwork_ThisPcTitle'), res('NoNetwork_Body')), chrome: { isNetworkConnected: false, networkName: '', wifiStrength: 0 } },
  { kind: 'overlay', phase: 'prerequisites', overlay: 'closeApplications', variant: 'initial', title: 'Close applications — initial ask', base: 'checkPrerequisites', baseState: () => checkPrereq({ isChecking: true }), state: () => closeApps() },
  { kind: 'overlay', phase: 'prerequisites', overlay: 'failure', variant: 'precheckBlocked', title: "Precheck couldn't finish", base: 'checkPrerequisites', baseState: () => checkPrereq({ isChecking: true }), state: () => failure({ message: "We couldn't get your PC ready. Please check again." }) }, // PrecheckEvaluator.cs:156 via PrecheckFailureRoute.cs:72

  // 3 · Pairing ───────────────────────────────────────────────────────────────
  { kind: 'screen', phase: 'pairing', screen: 'connectOldPc', variant: 'searching', title: 'Connect old PC — searching', state: () => connectOldPc() },
  { kind: 'screen', phase: 'pairing', screen: 'connectOldPc', variant: 'noDevice', title: 'Connect old PC — no device found (popup)', state: () => connectOldPc({ showNoDeviceFoundModal: true }), popupOffState: () => connectOldPc() },
  { kind: 'overlay', phase: 'pairing', overlay: 'trustNetwork', variant: 'overConnect', title: 'Trust network — over Connect old PC', base: 'connectOldPc', baseState: () => connectOldPc(), state: () => ({ canTrust: true, statusMessage: '' }) },
  { kind: 'overlay', phase: 'pairing', overlay: 'failure', variant: 'versionOldPcOlder', title: 'Version mismatch 2701 — update old PC', base: 'connectOldPc', baseState: () => connectOldPc(), state: () => failure({ titleKey: 'VersionMismatch_UpdateDda_Title', messageKeys: ['VersionMismatch_UpdateDda_Body', 'VersionMismatch_TryAgain'], errorCode: 2701 }) },
  { kind: 'overlay', phase: 'pairing', overlay: 'failure', variant: 'versionOldPcOlderEnterCode', title: 'Version mismatch 2701 — update old PC (over Enter code)', base: 'enterCode', baseState: () => enterCode({ enteredCode: '123456', isLinking: true }), state: () => failure({ titleKey: 'VersionMismatch_UpdateDda_Title', messageKeys: ['VersionMismatch_UpdateDda_Body', 'VersionMismatch_TryAgain'], errorCode: 2701 }) },
  { kind: 'overlay', phase: 'pairing', overlay: 'noNetwork', variant: 'thisPcPairing', title: 'No network — this PC (pairing)', base: 'connectOldPc', baseState: () => connectOldPc(), state: () => precheck(res('NoNetwork_ThisPcTitle'), res('NoNetwork_Body')), chrome: { isNetworkConnected: false, networkName: '', wifiStrength: 0 } },
  { kind: 'overlay', phase: 'pairing', overlay: 'noNetwork', variant: 'thisPcPairingEnterCode', title: 'No network — this PC (pairing lost, over Enter code)', base: 'enterCode', baseState: () => enterCode({ enteredCode: '123456', statusMessage: "We lost track of your old PC. Let's look for it again." }), state: () => precheck(res('NoNetwork_ThisPcTitle'), res('NoNetwork_Body')), chrome: { isNetworkConnected: false, networkName: '', wifiStrength: 0 } }, // PairingEvaluator.cs:147, EnterCodePageViewModel.cs:~430

  { kind: 'screen', phase: 'pairing', screen: 'enterCode', variant: 'empty', title: 'Enter code — empty', state: () => enterCode() },
  { kind: 'screen', phase: 'pairing', screen: 'enterCode', category: 'input', variant: 'partial', title: 'Enter code — partly typed (Link off)', state: () => enterCode({ enteredCode: '123' }) },
  { kind: 'screen', phase: 'pairing', screen: 'enterCode', category: 'input', variant: 'full', title: 'Enter code — code typed', state: () => enterCode({ enteredCode: '123456', canLink: true }) },
  { kind: 'screen', phase: 'pairing', screen: 'enterCode', variant: 'verifying', title: 'Enter code — verifying', state: () => enterCode({ enteredCode: '123456', isLinking: true, statusMessage: res('EnterCode_StatusVerifying') }) },
  { kind: 'screen', phase: 'pairing', screen: 'enterCode', variant: 'success', title: 'Enter code — connected', state: () => enterCode({ enteredCode: '123456', isSuccess: true, statusMessage: res('EnterCode_StatusSuccess') }) },
  // PairingEvaluator.cs:155 (wrong code), :164-168 (locked, resx format).
  { kind: 'screen', phase: 'pairing', screen: 'enterCode', variant: 'wrongCode', title: 'Enter code — wrong code', state: () => enterCode({ statusMessage: "That code didn't match. Check your old PC and try again." }) },
  { kind: 'screen', phase: 'pairing', screen: 'enterCode', variant: 'wrongCodeWait', title: 'Enter code — wrong code, back-off hint', state: () => enterCode({ statusMessage: "That code didn't match. Check your old PC and try again. Please wait 30s before trying again." }) }, // PairingEvaluator.cs:155-158
  { kind: 'screen', phase: 'pairing', screen: 'enterCode', variant: 'locked', title: 'Enter code — locked out', state: () => enterCode({ isLocked: true, statusMessage: res('EnterCode_StatusLocked', '2:00') }) },
  { kind: 'screen', phase: 'pairing', screen: 'enterCode', variant: 'noDevice', title: 'Enter code — no device found (popup)', state: () => enterCode({ enteredCode: '123456', showNoDeviceFoundModal: true }), popupOffState: () => enterCode({ enteredCode: '123456' }) },
  { kind: 'overlay', phase: 'pairing', overlay: 'trustNetwork', variant: 'overEnterCode', title: 'Trust network — over Enter code', base: 'enterCode', baseState: () => enterCode(), state: () => ({ canTrust: true, statusMessage: '' }) },
  { kind: 'overlay', phase: 'pairing', overlay: 'failure', variant: 'versionThisPcOlder', title: 'Version mismatch 2702 — update this PC', base: 'enterCode', baseState: () => enterCode({ enteredCode: '123456', isLinking: true }), state: () => failure({ titleKey: 'VersionMismatch_UpdateSa_Title', messageKeys: ['VersionMismatch_UpdateSa_Body', 'VersionMismatch_TryAgain'], errorCode: 2702 }) },

  // 4 · Compatibility ─────────────────────────────────────────────────────────
  { kind: 'screen', phase: 'compatibility', screen: 'readyToMove', variant: 'gathering', title: 'Ready to move — gathering', state: () => readyToMove() },
  { kind: 'overlay', phase: 'compatibility', overlay: 'localeMismatch', variant: 'default', title: 'Languages differ between PCs', base: 'readyToMove', baseState: () => readyToMove(), state: () => precheck(res('LocaleMismatch_Title'), res('LocaleMismatch_Body')) },
  // AccountMismatchPageViewModel.cs:173-175 (hard-coded status lines); account labels are sample.
  { kind: 'overlay', phase: 'compatibility', overlay: 'accountMismatch', variant: 'consent', title: 'Account mismatch — consent', base: 'readyToMove', baseState: () => readyToMove(), state: () => ({ statusMessage: "We'll move your old PC account's data into your account on this Dell.", oldAccountLabel: 'alex@oldpc.example', newAccountLabel: 'alex@dell.example', canConsent: true }) },
  { kind: 'overlay', phase: 'compatibility', overlay: 'accountMismatch', variant: 'noOldAccount', title: 'Account mismatch — no old account', base: 'readyToMove', baseState: () => readyToMove(), state: () => ({ statusMessage: "We couldn't find a signed-in account on your old PC to move.", oldAccountLabel: 'your account', newAccountLabel: 'alex@dell.example', canConsent: false }) },
  { kind: 'overlay', phase: 'compatibility', overlay: 'migrationCancelled', variant: 'overReady', title: 'Old PC closed before the move began', base: 'readyToMove', baseState: () => readyToMove(), state: () => precheck(res('MigrationCancelled_Title'), res('MigrationCancelled_Body')) },
  // Failure popups the engine/UI can raise once paired (all fatal, any stage — MainWindowViewModel.cs error escalation). The host here is where each is most likely seen.
  { kind: 'overlay', phase: 'compatibility', overlay: 'failure', variant: 'hardIncompatible', title: 'PCs not compatible', base: 'readyToMove', baseState: () => readyToMove(), state: () => failure({ message: "This PC isn't compatible with the data on your old PC, so we can't continue." }) }, // CompatibilityEvaluator.cs:88
  { kind: 'overlay', phase: 'compatibility', overlay: 'failure', variant: 'infoTimedOut', title: 'Old PC never delivered its drive info (2601)', base: 'readyToMove', baseState: () => readyToMove(), state: () => failure({ message: res('EngineError_MigrationInfoTimedOut') }) },
  { kind: 'overlay', phase: 'compatibility', overlay: 'failure', variant: 'infoFailed', title: 'Could not check the old PC (2600 / 2607)', base: 'readyToMove', baseState: () => readyToMove(), state: () => failure({ message: res('EngineError_MigrationInfoFailedOrIncomplete') }) },
  { kind: 'overlay', phase: 'compatibility', overlay: 'failure', variant: 'restartTimedOut', title: "Couldn't get ready to reconnect", base: 'readyToMove', baseState: () => readyToMove(), state: () => failure({ message: "We couldn't get your PC ready to reconnect. Please close Dell Data Assistant and try again." }) }, // PairingRestarter.cs:184
  { kind: 'overlay', phase: 'compatibility', overlay: 'noNetwork', variant: 'thisPcPostPairing', title: 'No network — this PC (after pairing)', base: 'readyToMove', baseState: () => readyToMove(), state: () => precheck(res('NoNetwork_ThisPcTitle'), res('NoNetwork_Body')), chrome: { isNetworkConnected: false, networkName: '', wifiStrength: 0 } },

  // 5 · Choose what to move ───────────────────────────────────────────────────
  { kind: 'screen', phase: 'selection', screen: 'chooseWhatToMove', variant: 'loading', title: 'Choose — first paint while drives are scanned (React draws no spinner)', state: () => choose({ isLoading: true, loadingCaption: 'Looking through your drives…', estimateText: res('Duration_EstimatingFiles') }) },
  { kind: 'screen', phase: 'selection', screen: 'chooseWhatToMove', variant: 'estimateHours', title: 'Choose — estimate in hours and minutes', state: () => choose({ estimateText: duration(65) }) },
  { kind: 'screen', phase: 'selection', screen: 'chooseWhatToMove', variant: 'estimateLessThanMinute', title: 'Choose — estimate under a minute', state: () => choose({ estimateText: duration(0) }) },
  { kind: 'screen', phase: 'selection', screen: 'chooseWhatToMove', variant: 'everything', title: 'Choose — move everything (summary)', state: () => choose() },
  { kind: 'screen', phase: 'selection', screen: 'chooseWhatToMove', variant: 'multiDrive', title: 'Choose — several destination drives', state: () => choose({ neededSizeText: '31.5 GB', driveStorageRows: [storageRow(), storageRow({ driveLetter: 'D:', headingText: storageHeading('D:'), currentSizeText: '1 TB', neededSizeText: '3.5 GB', remainingSizeText: '996 GB' })] }) },
  { kind: 'screen', phase: 'selection', screen: 'chooseWhatToMove', variant: 'doesNotFit', title: 'Choose — does not fit', state: () => choose({ fitsOnDestination: false, canMigrate: false, driveStorageRows: [storageRow({ driveLetter: 'E:', headingText: storageHeading('E:'), currentSizeText: '450 GB', neededSizeText: '80 GB', remainingSizeText: '0 B', currentFraction: 0.9, neededFraction: 1, remainingFraction: 0, fitsOnDestination: false, shortfallText: res('ChooseWhatToMove_DriveDoesNotFitWarning', '30 GB') })] }) },
  { kind: 'screen', phase: 'selection', screen: 'chooseWhatToMove', category: 'selection', variant: 'treeCollapsed', title: 'Choose — pick files & settings (collapsed)', state: () => selectFiles() },
  // Steps expand Files, its C: drive, then Settings, then one settings group — the order matters: each click
  // changes which expander buttons exist, so nth indexes below are in DOM order at that moment.
  { kind: 'screen', phase: 'selection', screen: 'chooseWhatToMove', category: 'selection', variant: 'treeExpanded', title: 'Choose — files & settings tree expanded', state: () => selectFiles(), steps: [
      click('button[class*="expander"]', { nth: 1 }), click('button[class*="expander"]', { nth: 2 }),
      click('button[class*="expander"]', { nth: 0 }), click('button[class*="expander"]', { nth: 1 }),
    ] },
  // The tree card scrolls inside a fixed-height panel, so with Settings open the Files branch falls below the
  // fold; this variant opens only Files and its C: drive so that branch is on screen for a screenshot.
  { kind: 'screen', phase: 'selection', screen: 'chooseWhatToMove', category: 'selection', variant: 'treeFilesExpanded', title: 'Choose — files branch expanded', state: () => selectFiles(), steps: [
      click('button[class*="expander"]', { nth: 1 }), click('button[class*="expander"]', { nth: 2 }),
    ] },
  { kind: 'screen', phase: 'selection', screen: 'chooseWhatToMove', category: 'selection', variant: 'treePartial', title: 'Choose — partial selection (indeterminate)', state: () => selectFiles({ allSelectedState: null, neededSizeText: '14 GB' }), steps: [
      click('button[class*="expander"]', { nth: 1 }), click('button[class*="expander"]', { nth: 2 }),
      click('button[class*="expander"]', { nth: 0 }), click('button[class*="expander"]', { nth: 1 }),
    ] },
  { kind: 'screen', phase: 'selection', screen: 'chooseWhatToMove', variant: 'treeRecalculating', title: 'Choose — recalculating selection', state: () => selectFiles({ isRecalculating: true, canMigrate: false, estimateText: res('Duration_EstimatingFiles') }) },
  { kind: 'screen', phase: 'selection', screen: 'chooseWhatToMove', category: 'selection', variant: 'treeExpanding', title: 'Choose — folder loading (card spinner)', state: () => selectFiles({ canMigrate: false, nodes: selectionTree().map((n, i) => (i === 1 ? { ...n, children: n.children.map((c, j) => (j === 1 ? { ...c, isLoading: true } : c)) } : n)) }), steps: [click('button[class*="expander"]', { nth: 1 })] },
  { kind: 'screen', phase: 'selection', screen: 'chooseWhatToMove', category: 'selection', variant: 'settingsOnly', title: 'Choose — settings only (about a minute)', state: () => selectFiles({ estimateText: res('Duration_AboutAMinute'), neededSizeText: '0 B', allSelectedState: null, nodes: selectionTree().map((n, i) => (i === 1 ? { ...n, isSelected: false } : n)) }) },
  { kind: 'screen', phase: 'selection', screen: 'chooseWhatToMove', category: 'selection', variant: 'treeNothingSelected', title: 'Choose — nothing selected', state: () => selectFiles({ allSelectedState: false, canMigrate: false, estimateText: '', neededSizeText: '0 B', nodes: selectionTree().map((n) => ({ ...n, isSelected: false })) }) },
  { kind: 'screen', phase: 'selection', screen: 'chooseWhatToMove', variant: 'driveMapping', title: 'Choose — change drive mapping (popup)', state: () => choose({ isDriveMappingModalOpen: true, driveMappingRows: driveMappingRows() }), popupOffState: () => choose({ driveMappingRows: driveMappingRows() }) },
  { kind: 'screen', phase: 'selection', screen: 'chooseWhatToMove', variant: 'driveMappingSingle', title: 'Choose — one old-PC drive (popup)', state: () => choose({ isDriveMappingModalOpen: true, driveMappingHeading: res('DriveMapping_HeadingSingle'), driveMappingRows: [driveMappingRows()[0]] }), popupOffState: () => choose({ driveMappingHeading: res('DriveMapping_HeadingSingle') }) },
  { kind: 'screen', phase: 'selection', screen: 'chooseWhatToMove', variant: 'driveMappingChanged', title: 'Choose — drive mapping, Apply enabled (popup)', state: () => choose({ isDriveMappingModalOpen: true, canApplyDriveMapping: true, driveMappingRows: driveMappingRows() }), popupOffState: () => choose({ driveMappingRows: driveMappingRows() }) },
  { kind: 'screen', phase: 'selection', screen: 'chooseWhatToMove', variant: 'driveMappingRescanning', title: 'Choose — drive mapping, rescanning (popup)', state: () => choose({ isDriveMappingModalOpen: true, isRescanning: true, driveMappingRows: driveMappingRows() }), popupOffState: () => choose({ driveMappingRows: driveMappingRows() }) },
  { kind: 'screen', phase: 'selection', screen: 'chooseWhatToMove', variant: 'driveMappingApplying', title: 'Choose — drive mapping, applying (popup)', state: () => choose({ isDriveMappingModalOpen: true, isApplyingDriveMapping: true, canApplyDriveMapping: true, driveMappingRows: driveMappingRows() }), popupOffState: () => choose({ driveMappingRows: driveMappingRows() }) },
  // Inside the drive-mapping popup: a dropdown list held open (the list is its own popover over the popup), and
  // the checkbox column in different multi-select states. Background-only = the Choose screen with no popup.
  { kind: 'screen', phase: 'selection', screen: 'chooseWhatToMove', category: 'dropdown', variant: 'driveDropdownOpen', title: 'Drive mapping — destination dropdown open (C:)', state: () => choose({ isDriveMappingModalOpen: true, driveMappingRows: driveMappingRows() }), popupOffState: () => choose({ driveMappingRows: driveMappingRows() }), steps: [openDriveDropdown(0)] },
  { kind: 'screen', phase: 'selection', screen: 'chooseWhatToMove', category: 'dropdown', variant: 'driveDropdownManyOptions', title: 'Drive mapping — dropdown open with 4 destinations (E:)', state: () => choose({ isDriveMappingModalOpen: true, driveMappingRows: threeDriveRows() }), popupOffState: () => choose({ driveMappingRows: threeDriveRows() }), steps: [openDriveDropdown(2)] },
  { kind: 'screen', phase: 'selection', screen: 'chooseWhatToMove', category: 'selection', variant: 'driveOneUnchecked', title: 'Drive mapping — one drive unchecked (its dropdown inactive)', state: () => choose({ isDriveMappingModalOpen: true, canApplyDriveMapping: true, driveMappingRows: threeDriveRows().map((row, i) => ({ ...row, selected: i !== 1 })) }), popupOffState: () => choose({ driveMappingRows: threeDriveRows() }) },
  { kind: 'screen', phase: 'selection', screen: 'chooseWhatToMove', category: 'selection', variant: 'driveNoneChecked', title: 'Drive mapping — no drive checked', state: () => choose({ isDriveMappingModalOpen: true, driveMappingRows: threeDriveRows().map((row) => ({ ...row, selected: false })) }), popupOffState: () => choose({ driveMappingRows: threeDriveRows() }) },
  { kind: 'overlay', phase: 'selection', overlay: 'installBrowser', variant: 'default', title: 'Install a browser first', base: 'chooseWhatToMove', baseState: () => choose({ canMigrate: false }), state: () => ({ browsersToInstall: ['Chrome', 'Firefox'] }) },
  { kind: 'overlay', phase: 'selection', overlay: 'closeApplications', variant: 'overChoose', title: 'Close applications — before starting', base: 'chooseWhatToMove', baseState: () => choose({ canMigrate: false }), state: () => closeApps() },
  { kind: 'overlay', phase: 'selection', overlay: 'closeApplications', variant: 'retry', title: 'Close applications — retry', base: 'chooseWhatToMove', baseState: () => choose({ canMigrate: false }), state: () => closeApps({ primaryButtonText: 'Retry', hasFailedAttempt: true, statusMessage: "We couldn't close the app. Close it yourself, then retry." }) }, // CloseApplicationsPageViewModel.cs:67,231
  { kind: 'overlay', phase: 'selection', overlay: 'closeApplications', variant: 'closing', title: 'Close applications — closing in progress', base: 'chooseWhatToMove', baseState: () => choose({ canMigrate: false }), state: () => closeApps({ statusMessage: 'Closing the app…', canClose: false }) },
  { kind: 'overlay', phase: 'selection', overlay: 'noNetwork', variant: 'otherPc', title: 'No network — the other PC', base: 'chooseWhatToMove', baseState: () => choose(), state: () => precheck(res('NoNetwork_OtherPcTitle'), res('NoNetwork_OtherPcBody')) },
  // Error.Details codes mapped by EngineErrorRoute.MessageFor — fatal at any stage; Choose is where they most often land.
  { kind: 'overlay', phase: 'selection', overlay: 'failure', variant: 'folderDetailsFailed', title: "Couldn't read the old PC's files (2606)", base: 'chooseWhatToMove', baseState: () => choose(), state: () => failure({ message: res('EngineError_FolderDetailsFailed') }) },
  { kind: 'overlay', phase: 'selection', overlay: 'failure', variant: 'accessDenied', title: 'Old PC folder not readable (2952)', base: 'chooseWhatToMove', baseState: () => choose(), state: () => failure({ message: res('EngineError_AccessDenied') }) },
  { kind: 'overlay', phase: 'selection', overlay: 'failure', variant: 'estimateUnavailable', title: 'Time estimate failed (2609)', base: 'chooseWhatToMove', baseState: () => choose(), state: () => failure({ message: res('EngineError_EstimateUnavailable') }) },
  { kind: 'overlay', phase: 'selection', overlay: 'failure', variant: 'noNetworkConnection', title: 'Engine: no network connection (2482)', base: 'chooseWhatToMove', baseState: () => choose(), state: () => failure({ message: res('EngineError_NoNetworkConnection') }) },
  { kind: 'overlay', phase: 'selection', overlay: 'failure', variant: 'networkChanged', title: 'Network changed (2497)', base: 'chooseWhatToMove', baseState: () => choose(), state: () => failure({ message: res('EngineError_NetworkChanged') }) },
  { kind: 'overlay', phase: 'selection', overlay: 'failure', variant: 'unknownCode', title: 'Unmapped engine error (code in the text)', base: 'chooseWhatToMove', baseState: () => choose(), state: () => failure({ message: res('EngineError_UnknownFailure', 2999) }) },
  { kind: 'overlay', phase: 'selection', overlay: 'migrationCancelled', variant: 'overChoose', title: 'Old PC closed before the move began (Choose)', base: 'chooseWhatToMove', baseState: () => choose(), state: () => precheck(res('MigrationCancelled_Title'), res('MigrationCancelled_Body')) },

  // 6 · Migrating ─────────────────────────────────────────────────────────────
  { kind: 'screen', phase: 'migrating', screen: 'migrating', variant: 'active', title: 'Migrating — files & settings', state: () => migrating() },
  { kind: 'screen', phase: 'migrating', screen: 'migrating', variant: 'filesOnly', title: 'Migrating — files only', state: () => migrating({ hasSelectedSettings: false, settingsPercent: 0 }) },
  { kind: 'screen', phase: 'migrating', screen: 'migrating', variant: 'settingsOnly', title: 'Migrating — settings only', state: () => migrating({ hasSelectedFiles: false, filePercent: 0, settingsPercent: 60, remainingText: res('Duration_AboutAMinute'), transferSpeedText: '0 B/s' }) },
  { kind: 'screen', phase: 'migrating', screen: 'migrating', variant: 'stopping', title: 'Migrating — stopping (Cancel hidden)', state: () => migrating({ canCancel: false }) },
  { kind: 'screen', phase: 'migrating', screen: 'migrating', variant: 'settingsSkipped', title: 'Migrating — settings need attention, files running', state: () => migrating({ settingsPercent: 100, settingsHasSkipped: true, hasSkippedItems: true }) },
  { kind: 'screen', phase: 'migrating', screen: 'migrating', variant: 'starting', title: 'Migrating — just started, no estimate yet', state: () => migrating({ filePercent: 0, settingsPercent: 0, remainingText: res('Duration_Estimating'), transferSpeedText: '0 B/s' }) },
  { kind: 'screen', phase: 'migrating', screen: 'migrating', variant: 'settingsPhase', title: 'Migrating — settings phase, files not reporting yet', state: () => migrating({ filePercent: 0, settingsPercent: 40, remainingText: res('Duration_AboutAMinute'), transferSpeedText: '0 B/s' }) },
  { kind: 'screen', phase: 'migrating', screen: 'migrating', variant: 'settingsDone', title: 'Migrating — settings done, files running', state: () => migrating({ settingsPercent: 100 }) },
  { kind: 'screen', phase: 'migrating', screen: 'migrating', variant: 'remainingHours', title: 'Migrating — hours remaining', state: () => migrating({ remainingText: duration(125) }) },
  { kind: 'screen', phase: 'migrating', screen: 'migrating', variant: 'remainingLessThanMinute', title: 'Migrating — under a minute left', state: () => migrating({ filePercent: 98, remainingText: res('Duration_LessThanAMinute') }) },
  { kind: 'screen', phase: 'migrating', screen: 'migrating', variant: 'complete', title: 'Migrating — end of run (on screen for one moment)', state: () => migratingDone() },
  { kind: 'screen', phase: 'migrating', screen: 'migrating', variant: 'cancelConfirm', title: 'Migrating — confirm cancel (popup)', state: () => migrating(), steps: [clickKey('Buttons_Cancel', { popup: true })] },
  { kind: 'overlay', phase: 'migrating', overlay: 'noNetwork', variant: 'thisPcMigrating', title: 'No network — this PC (during move)', base: 'migrating', baseState: () => migrating(), state: () => precheck(res('NoNetwork_ThisPcTitle'), res('NoNetwork_Body')), chrome: { isNetworkConnected: false, networkName: '', wifiStrength: 0 } },
  { kind: 'overlay', phase: 'migrating', overlay: 'noNetwork', variant: 'otherPcMigrating', title: 'No network — the other PC (during move)', base: 'migrating', baseState: () => migrating(), state: () => precheck(res('NoNetwork_OtherPcTitle'), res('NoNetwork_OtherPcBody')) },
  { kind: 'overlay', phase: 'migrating', overlay: 'connectionLost', variant: 'default', title: 'Connection lost', base: 'migrating', baseState: () => migrating(), state: connectionLost },
  { kind: 'overlay', phase: 'migrating', overlay: 'failure', variant: 'engineConnectionLost', title: 'Engine connection lost', base: 'migrating', baseState: () => migrating(), state: () => failure({ message: 'The connection to the migration engine was lost. Please close and try again.' }) }, // FailurePageViewModel.cs:176
  { kind: 'overlay', phase: 'migrating', overlay: 'failure', variant: 'generic', title: 'Something went wrong', base: 'migrating', baseState: () => migrating(), state: () => failure({ message: res('EngineError_UnhandledEngineError') }) },

  // 7 · Results & finish ──────────────────────────────────────────────────────
  { kind: 'screen', phase: 'results', screen: 'resultsSummary', variant: 'loading', title: 'Results — preparing details', state: () => results({ isLoading: true, isReady: false, tiles: [], canFinish: false }) },
  { kind: 'screen', phase: 'results', screen: 'resultsSummary', variant: 'cancelling', title: 'Results — cancelling', state: () => results({ isLoading: true, wasCancelled: true, isReady: false, tiles: [], canFinish: false }) },
  { kind: 'screen', phase: 'results', screen: 'resultsSummary', variant: 'ready', title: 'Results — clean finish', state: () => results() },
  { kind: 'screen', phase: 'results', screen: 'resultsSummary', variant: 'withSkipped', title: 'Results — some items not transferred', state: () => results({ hasSkippedItems: true, statusMessage: '', tiles: summaryTiles({ notMigrated: '3', existing: '42.5 MB' }), skippedSubtextText: 'Some of your items were skipped during your migration on October 23, 2026, at 3:45 PM.' }) },
  { kind: 'screen', phase: 'results', screen: 'resultsSummary', variant: 'rebootRequired', title: 'Results — restart required', state: () => results({ rebootRequired: true, rebootReasonText: 'System needs to be rebooted to apply settings' }) }, // MigrationWorker.cs:1169 (engine text)
  { kind: 'screen', phase: 'results', screen: 'resultsSummary', variant: 'unavailable', title: 'Results — summary unavailable', state: () => results({ tiles: unavailableTiles(), migrationRanText: '', statusMessage: "We couldn't retrieve your migration summary." }) }, // ResultsSummaryPageViewModel.cs:362-369
  { kind: 'overlay', phase: 'results', overlay: 'failure', variant: 'eraseStartedOnOldPc', title: 'Erase running on the old PC (dismissible)', base: 'resultsSummary', baseState: () => results(), state: () => failure({ title: res('EngineError_EraseStartedOnOldPc_Title'), message: res('EngineError_EraseStartedOnOldPc'), errorCode: 2207, dismissible: true }) }, // arrives after the move: EngineErrorRoute.cs:107
  { kind: 'screen', phase: 'results', screen: 'complete', variant: 'loading', title: 'Complete — getting the details', state: () => ({ ...complete(), nodes: [completeReport()[0]], statusMessage: 'Getting the details…' }) }, // CompletePageViewModel.cs:147
  { kind: 'screen', phase: 'results', screen: 'complete', variant: 'default', title: 'Complete — report tree', state: complete },
  { kind: 'screen', phase: 'results', screen: 'complete', category: 'selection', variant: 'nestedExpanded', title: 'Complete — settings group expanded', state: complete, steps: [click('button[aria-label="Desktop and personalization (2)"]')] },
  { kind: 'screen', phase: 'results', screen: 'complete', variant: 'noPdf', title: 'Complete — PDF report not available', state: () => ({ ...complete(), canOpenPdf: false }) },
  { kind: 'screen', phase: 'results', screen: 'skippedFiles', variant: 'loading', title: 'Skipped files — getting the details', state: () => skipped({ nodes: [filesRoot('SkippedFiles_FilesCopied', 1284, '12.4 GB')], skippedNodes: [], estimatedTimeText: '' }) },
  { kind: 'screen', phase: 'results', screen: 'skippedFiles', variant: 'ready', title: 'Skipped files — retry available', state: () => skipped() },
  // Expanders in DOM order: [0] Settings copied (read-only), [1] Files-not-copied root, [2] C:\ drive, [3] Settings-not-copied root…
  { kind: 'screen', phase: 'results', screen: 'skippedFiles', category: 'selection', variant: 'filesExpanded', title: 'Skipped files — drive expanded', state: () => skipped(), steps: [click('button[class*="expander"]', { nth: 2 })] },
  { kind: 'screen', phase: 'results', screen: 'skippedFiles', category: 'selection', variant: 'partial', title: 'Skipped files — one file unchecked (group mixed)', state: () => skipped({ estimatedTimeText: 'Estimated time: less than a minute (1 MB selected)', skippedNodes: skippedTree({ leafChecked: [true, false] }) }), steps: [click('button[class*="expander"]', { nth: 2 })] },
  { kind: 'screen', phase: 'results', screen: 'skippedFiles', variant: 'estimateMinutes', title: 'Skipped files — multi-minute estimate', state: () => skipped({ estimatedTimeText: 'Estimated time: 2 minutes (120 MB selected)' }) },
  { kind: 'screen', phase: 'results', screen: 'skippedFiles', category: 'selection', variant: 'settingsOnlyChecked', title: 'Skipped files — only a setting checked (0 KB)', state: () => skipped({ estimatedTimeText: 'Estimated time: less than a minute (0 KB selected)', skippedNodes: skippedTree({ leafChecked: [false, false], withDirectory: false }).map((n) => (n.nodeId === '1' ? { ...n, isChecked: true } : n)) }), steps: [click('button[class*="expander"]', { nth: 2 })] }, // SkippedFilesPageViewModel.cs:618
  { kind: 'screen', phase: 'results', screen: 'skippedFiles', category: 'selection', variant: 'loadingDirectory', title: 'Skipped files — opening a folder (card spinner)', state: () => skipped({ skippedNodes: skippedTree({ directoryLoading: true }) }), steps: [click('button[class*="expander"]', { nth: 2 })] },
  { kind: 'screen', phase: 'results', screen: 'skippedFiles', variant: 'retrying', title: 'Skipped files — retry sent (actions off)', state: () => skipped({ canAct: false }) },
  { kind: 'screen', phase: 'results', screen: 'skippedFiles', category: 'selection', variant: 'noSelection', title: 'Skipped files — nothing checked (Retry off)', state: () => skipped({ hasSelection: false, estimatedTimeText: '', skippedNodes: skippedTree({ leafChecked: [false, false], withDirectory: false }) }), steps: [click('button[class*="expander"]', { nth: 2 })] },
  { kind: 'screen', phase: 'results', screen: 'skippedFiles', variant: 'cancelled', title: 'Skipped files — move was cancelled (no Retry)', state: () => skipped({ retryVisible: false }) },
  { kind: 'screen', phase: 'results', screen: 'skippedFiles', variant: 'networkLost', title: 'Skipped files — old PC gone (Finish only)', state: () => skipped({ networkLost: true }) },
  ...skipReasonScenarios,
  { kind: 'overlay', phase: 'results', overlay: 'noNetwork', variant: 'otherPcAfter', title: 'No network — the other PC (after the move)', base: 'skippedFiles', baseState: () => skipped(), state: () => precheck(res('NoNetwork_OtherPcTitle'), res('NoNetwork_OtherPcBody')) },
  { kind: 'screen', phase: 'results', screen: 'migrationDone', variant: 'ready', title: 'Migration done — next steps', state: () => ({ canAct: true }) },
  { kind: 'screen', phase: 'results', screen: 'migrationDone', variant: 'leaving', title: 'Migration done — actions disabled (restarting)', state: () => ({ canAct: false }) },
  // The Feedback form, one entry per state of its two inputs (a star rating and a comment; Submit needs both).
  { kind: 'screen', phase: 'results', screen: 'migrationDone', variant: 'feedback', title: 'Migration done — feedback form, empty (popup)', state: () => ({ canAct: true }), steps: [openFeedback] },
  { kind: 'screen', phase: 'results', screen: 'migrationDone', category: 'input', variant: 'feedbackHalfStar', title: 'Feedback form — 3½ stars and a comment', state: () => ({ canAct: true }), steps: [openFeedback, star(6), comment('Mostly smooth, a couple of slow moments.')] },
  { kind: 'screen', phase: 'results', screen: 'migrationDone', category: 'input', variant: 'feedbackFilled', title: 'Feedback form — 4 stars and a comment (Submit on)', state: () => ({ canAct: true }), steps: [openFeedback, star(7), comment('The transfer was quick and easy.')] },
  { kind: 'screen', phase: 'results', screen: 'migrationDone', category: 'input', variant: 'feedbackFullLength', title: 'Feedback form — 5 stars, comment at the 140 limit', state: () => ({ canAct: true }), steps: [openFeedback, star(9), comment('Great experience. '.repeat(8).slice(0, 140))] },
  { kind: 'screen', phase: 'results', screen: 'learnAboutErase', variant: 'ready', title: 'Learn about erase', state: () => ({ canAct: true }) },
  { kind: 'screen', phase: 'results', screen: 'learnAboutErase', variant: 'leaving', title: 'Learn about erase — Back to home disabled', state: () => ({ canAct: false }) },

  // 8 · App-wide popups ───────────────────────────────────────────────────────
  { kind: 'overlay', phase: 'global', overlay: 'signOut', variant: 'waiting', title: 'Sign out — waiting', base: 'welcome', baseState: () => welcome({ isSignedIn: true, userName: sampleUser }), state: () => ({ isSigningOut: true, isOpeningBrowser: true }) },
  { kind: 'overlay', phase: 'global', overlay: 'signOut', variant: 'error', title: 'Sign out — error', base: 'welcome', baseState: () => welcome({ isSignedIn: true, userName: sampleUser }), state: () => ({ isSigningOut: false, isOpeningBrowser: false, errorMessage: res('SignOut_ErrorBody') }) },
  { kind: 'overlay', phase: 'global', overlay: 'noNetwork', variant: 'authSignIn', title: 'No network — during sign-in', chrome: { isSignedIn: false, isNetworkConnected: false, networkName: '', wifiStrength: 0 }, base: 'welcome', baseState: () => welcome(), state: () => precheck(res('NoNetwork_ThisPcTitle'), res('NoNetwork_Body')) },
  { kind: 'overlay', phase: 'global', overlay: 'failure', variant: 'engineStartFailed', title: 'Engine could not start', base: 'welcome', baseState: welcomeLaunching, state: () => failure({ message: res('Failure_EngineStartFailed') }) },
  { kind: 'overlay', phase: 'global', overlay: 'failure', variant: 'engineMissing', title: 'Engine files missing', base: 'welcome', baseState: welcomeLaunching, state: () => failure({ message: res('Failure_EngineMissing') }) },
  { kind: 'overlay', phase: 'global', overlay: 'failure', variant: 'engineConfigMissing', title: 'Engine settings file missing', base: 'welcome', baseState: welcomeLaunching, state: () => failure({ message: res('Failure_EngineConfigMissing') }) },
  { kind: 'overlay', phase: 'global', overlay: 'failure', variant: 'engineNotVerified', title: 'Engine signature invalid', base: 'welcome', baseState: welcomeLaunching, state: () => failure({ message: 'The migration engine could not be verified. Please reinstall Dell Data Assistant.' }) }, // FailurePageViewModel.cs:160
  { kind: 'overlay', phase: 'global', overlay: 'failure', variant: 'unexpected', title: 'Unexpected error (generic message)', chrome: { isSignedIn: false }, base: 'welcome', baseState: () => welcome(), state: () => failure({ message: 'An unexpected error occurred. Please close and try again.' }) }, // FailurePageViewModel.DefaultMessage
  { kind: 'overlay', phase: 'global', overlay: 'failure', variant: 'shortcutCreateFailed', title: "Desktop shortcut couldn't be added", base: 'migrationDone', baseState: () => ({ canAct: true }), state: () => failure({ message: res('DesktopShortcut_CreateFailed') }) }, // AppCloseCoordinator.cs:195
  { kind: 'overlay', phase: 'global', overlay: 'noNetwork', variant: 'authSignOut', title: 'No network — during sign-out', chrome: { isNetworkConnected: false, networkName: '', wifiStrength: 0 }, base: 'welcome', baseState: () => welcome({ isSignedIn: true, userName: sampleUser }), state: () => precheck(res('NoNetwork_ThisPcTitle'), res('NoNetwork_Body')) },
  { kind: 'closePrompt', phase: 'global', step: 'cancelMigration', variant: 'default', title: 'Close window — cancel migration?', base: 'migrating', baseState: () => migrating() },
  { kind: 'closePrompt', phase: 'global', step: 'shortcut', variant: 'default', title: 'Close window — add desktop shortcut', base: 'migrationDone', baseState: () => ({ canAct: true }) },
]

// ── Identity, URL contract, manifest ─────────────────────────────────────────

/** Stable, URL-safe id for a scenario — the manifest key. */
export function scenarioId(s: Scenario): string {
  if (s.kind === 'screen') return `screen.${s.screen}.${s.variant}`
  if (s.kind === 'overlay') return `overlay.${s.overlay}.${s.variant}`
  return `closeConfirm.${s.step}.${s.variant}`
}

/** The query (no '?') selecting this scenario's popup-shown view. */
export function scenarioQuery(s: Scenario): string {
  const p = new URLSearchParams()
  if (s.kind === 'screen') { p.set('screen', s.screen) }
  else if (s.kind === 'overlay') { p.set('overlay', s.overlay) }
  else { p.set('closeConfirm', s.step) }
  p.set('variant', s.variant)
  return p.toString()
}

/** Resolve a scenario from catalog URL params; undefined → the index page. An unknown variant falls back to
 *  the first scenario for that id; an unknown id resolves to nothing. */
export function resolveScenario(params: URLSearchParams): Scenario | undefined {
  const variant = params.get('variant') ?? undefined
  const pick = <T extends Scenario>(matches: T[]): T | undefined =>
    (variant ? matches.find((m) => m.variant === variant) : undefined) ?? matches[0]

  const screen = params.get('screen')
  if (screen) {
    return pick(scenarios.filter((s): s is ScreenScenario => s.kind === 'screen' && s.screen === screen))
  }
  const overlay = params.get('overlay')
  if (overlay) {
    return pick(scenarios.filter((s): s is OverlayScenario => s.kind === 'overlay' && s.overlay === overlay))
  }
  const closeConfirm = params.get('closeConfirm')
  if (closeConfirm) {
    return pick(scenarios.filter((s): s is ClosePromptScenario => s.kind === 'closePrompt' && s.step === closeConfirm))
  }
  return undefined
}

/** Flat, journey-ordered manifest for automation — window.__SCREEN_CATALOG__. */
export interface ManifestEntry {
  id: string
  kind: Scenario['kind']
  phase: Phase
  /** What kind of surface this is — see Category. */
  category: Category
  /** The screen it belongs to (itself, or the screen a popup sits over). */
  host: ScreenId
  title: string
  /** True when the scenario shows a popup; backgroundQuery is then the same screen without it. */
  hasPopup: boolean
  /** Query for the default (popup shown) view. */
  query: string
  /** Query for the background-only view (popups=hidden) — present only when hasPopup. */
  backgroundQuery?: string
}

export function buildManifest(): ManifestEntry[] {
  return scenarios.map((s) => {
    const query = scenarioQuery(s)
    const popup = hasPopup(s)
    return {
      id: scenarioId(s),
      kind: s.kind,
      phase: s.phase,
      category: categoryOf(s),
      host: hostScreen(s),
      title: s.title,
      hasPopup: popup,
      query,
      ...(popup ? { backgroundQuery: `${query}&popups=hidden` } : {}),
    }
  })
}
