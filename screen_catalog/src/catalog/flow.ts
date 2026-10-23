// The app's real navigation graph, transcribed from the native view models — the logic the catalog's
// scenario ordering and overlay placement are checked against (catalog.test.ts), so the catalog cannot
// drift into showing a screen or popup in a place the app never produces it.
//
// Every edge cites the C# that performs it (file:line as of this transcription). Screens appear as
// ScreenIds, the same names contract.ts / App.tsx use. This is documentation-as-data: nothing in the app
// imports it, and it never ships in the embedded wwwroot.
import type { OverlayId, ScreenId } from '@app/bridge/contract'

export interface FlowEdge {
  from: ScreenId
  to: ScreenId
  trigger: string
  /** The C# call site, e.g. "WelcomePageViewModel.cs:311". */
  source: string
}

/** Where the app can start: MainWindowViewModel's launch routing and the reminder-toast launch. */
export const entryScreens: ScreenId[] = ['welcome', 'checkPrerequisites', 'migrateReminder']

export const flowEdges: FlowEdge[] = [
  // Entry / onboarding
  { from: 'welcome', to: 'checkPrerequisites', trigger: 'Continue (signed in, or after sign-in)', source: 'WelcomePageViewModel.cs:311,325' },
  { from: 'welcome', to: 'welcomeDeferral', trigger: 'Remind me later', source: 'WelcomePageViewModel.cs:227' },
  { from: 'welcomeDeferral', to: 'deferralSuccess', trigger: 'Set reminder succeeded', source: 'WelcomeDeferralPageViewModel.cs:102' },
  { from: 'welcomeDeferral', to: 'welcomeDeferralError', trigger: 'Scheduling the reminder failed', source: 'WelcomeDeferralPageViewModel.cs:93' },
  { from: 'welcomeDeferral', to: 'welcome', trigger: 'Close', source: 'WelcomeDeferralPageViewModel.cs:108' },
  { from: 'deferralSuccess', to: 'welcome', trigger: 'Close', source: 'DeferralSuccessPageViewModel.cs:72' },
  { from: 'migrateReminder', to: 'migrateReminderSet', trigger: 'Continue', source: 'MigrateReminderPageViewModel.cs:108' },

  // Prerequisites → pairing
  { from: 'checkPrerequisites', to: 'connectOldPc', trigger: 'Precheck ready (auto-advance, unpaired)', source: 'CheckPrerequisitesPageViewModel.cs:263-265 + PostPairingRoute.cs:AdvancePage' },
  { from: 'checkPrerequisites', to: 'welcome', trigger: 'Cancel (after Migration.Stop ack)', source: 'CheckPrerequisitesPageViewModel.cs:284' },
  { from: 'connectOldPc', to: 'enterCode', trigger: 'Old PC discovered', source: 'ConnectOldPcPageViewModel.cs:174' },
  { from: 'connectOldPc', to: 'welcome', trigger: 'Cancel / No-device-found modal dismiss', source: 'ConnectOldPcPageViewModel.cs:147' },
  { from: 'enterCode', to: 'readyToMove', trigger: 'Code accepted, pairing confirmed', source: 'EnterCodePageViewModel.cs:400' },
  { from: 'enterCode', to: 'connectOldPc', trigger: 'Pairing restart', source: 'EnterCodePageViewModel.cs:431' },
  { from: 'enterCode', to: 'welcome', trigger: 'Cancel / No-device-found modal dismiss', source: 'EnterCodePageViewModel.cs:218' },

  // Compatibility → selection → migration
  { from: 'readyToMove', to: 'chooseWhatToMove', trigger: 'Compatibility check passed', source: 'ReadyToMovePageViewModel.cs:128,377' },
  { from: 'readyToMove', to: 'welcome', trigger: 'Cancel', source: 'ReadyToMovePageViewModel.cs:282' },
  { from: 'chooseWhatToMove', to: 'migrating', trigger: 'Migrate now (checks passed, Migration.Start sent)', source: 'ChooseWhatToMovePageViewModel.cs:1857' },
  { from: 'chooseWhatToMove', to: 'welcome', trigger: 'Cancel (session restart)', source: 'ChooseWhatToMovePageViewModel.cs:1431' },
  { from: 'migrating', to: 'resultsSummary', trigger: 'Migration finished or cancelled', source: 'MigratingPageViewModel.cs:575' },

  // Results
  { from: 'resultsSummary', to: 'complete', trigger: 'View the details', source: 'ResultsSummaryPageViewModel.cs:441' },
  { from: 'resultsSummary', to: 'skippedFiles', trigger: 'Show skipped files', source: 'ResultsSummaryPageViewModel.cs:456' },
  { from: 'resultsSummary', to: 'migrationDone', trigger: 'Finish', source: 'ResultsSummaryPageViewModel.cs:503,509' },
  { from: 'complete', to: 'resultsSummary', trigger: 'Back to summary', source: 'CompletePageViewModel.cs:221' },
  { from: 'skippedFiles', to: 'migrating', trigger: 'Retry skipped files', source: 'SkippedFilesPageViewModel.cs:517' },
  { from: 'skippedFiles', to: 'migrationDone', trigger: 'Finish', source: 'SkippedFilesPageViewModel.cs:564' },
  { from: 'migrationDone', to: 'resultsSummary', trigger: 'View summary', source: 'MigrationDonePageViewModel.cs:158' },
  { from: 'migrationDone', to: 'learnAboutErase', trigger: 'Learn about erase', source: 'MigrationDonePageViewModel.cs:170' },
  { from: 'migrationDone', to: 'welcome', trigger: 'Migrate more data / Back to home (session restart)', source: 'MigrationDonePageViewModel.cs:217' },
  { from: 'learnAboutErase', to: 'welcome', trigger: 'Back to home (session restart)', source: 'PostMigrationExitRoute.cs:48,76' },
]

type Over = ScreenId[] | 'any'

/**
 * Which screens each overlay is genuinely shown over. A scenario's `base` must be in this list — the test
 * enforces it. 'any' = raised from app-global code with no fixed host screen (the header, the network
 * watcher, the engine error router).
 */
export const overlayOver: Record<OverlayId, { over: Over; source: string }> = {
  signIn: { over: ['welcome'], source: 'WelcomePageViewModel.cs:288' },
  signOut: { over: 'any', source: 'MainWindowViewModel.cs:376 (header Sign out)' },
  trustNetwork: { over: ['checkPrerequisites', 'connectOldPc', 'enterCode'], source: 'CheckPrerequisitesPageViewModel.cs:239; ConnectOldPcPageViewModel.cs:194; EnterCodePageViewModel.cs:308' },
  notAdmin: { over: ['checkPrerequisites'], source: 'PrecheckFailureRoute.cs:57 via CheckPrerequisitesPageViewModel.cs:255' },
  osNotSupported: { over: ['checkPrerequisites'], source: 'PrecheckFailureRoute.cs:54' },
  localeNotSupported: { over: ['checkPrerequisites'], source: 'PrecheckFailureRoute.cs:66' },
  batteryCritical: { over: ['checkPrerequisites'], source: 'PrecheckFailureRoute.cs:60' },
  closeApplications: { over: ['checkPrerequisites', 'chooseWhatToMove'], source: 'PrecheckFailureRoute.cs:70; ChooseWhatToMovePageViewModel.cs:1725' },
  installBrowser: { over: ['chooseWhatToMove'], source: 'ChooseWhatToMovePageViewModel.cs:1664' },
  localeMismatch: { over: ['readyToMove'], source: 'ReadyToMovePageViewModel.cs:315' },
  accountMismatch: { over: ['readyToMove'], source: 'ReadyToMovePageViewModel.cs:331' },
  noNetwork: {
    over: ['welcome', 'checkPrerequisites', 'connectOldPc', 'enterCode', 'readyToMove', 'chooseWhatToMove', 'migrating', 'resultsSummary', 'complete', 'skippedFiles', 'migrationDone'],
    source: 'AuthModalSink.cs:79; PrecheckFailureRoute.cs:63; MainWindowViewModel.cs:569,833,1022,1028,1270,1317',
  },
  failure: { over: 'any', source: 'EngineErrorRoute / MainWindowViewModel.cs:578,1295,1322,1414; EngineLauncher.cs:123; AuthModalSink.cs:86' },
  connectionLost: { over: 'any', source: 'MainWindowViewModel.cs:548' },
  migrationCancelled: { over: ['readyToMove', 'chooseWhatToMove'], source: 'MainWindowViewModel.cs:1284 (old PC closed before Migration.Start)' },
}

/** True when `base` is a screen the overlay is genuinely shown over. */
export function overlayAllowedOver(overlay: OverlayId, base: ScreenId): boolean {
  const { over } = overlayOver[overlay]
  return over === 'any' || over.includes(base)
}

/** Every screen reachable from the entry screens along flowEdges. */
export function reachableScreens(): Set<ScreenId> {
  const seen = new Set<ScreenId>(entryScreens)
  const queue: ScreenId[] = [...entryScreens]
  while (queue.length > 0) {
    const current = queue.shift()!
    for (const edge of flowEdges) {
      if (edge.from === current && !seen.has(edge.to)) {
        seen.add(edge.to)
        queue.push(edge.to)
      }
    }
  }
  return seen
}
