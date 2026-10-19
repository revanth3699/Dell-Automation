# Target PC state machine — transition table (draft)

Status: **draft for review, 2026-10-19**. Derived by reading the rebit backend
(`rebit/Cdm/Cdm/TargetPc.UI` at commit `a7ed19282`), not from live runs. Every row cites
the backend file it came from; rows marked **[inferred]** are a reading of the code, not
something the code states. Nothing here has been confirmed on hardware yet.

Purpose: this is the data the proposed observer/runner (see the discussion in the PR for
`fix/target-locators-ui-copy-update`) would consume. Once agreed it becomes a data file
(YAML/Python) under `orchestration/`; until then it is the reference the team reviews.

## 1. How to read this

The app has three layers, and the automation's observed state is the triple
`(screen, overlay, close_prompt)`:

| Layer | Rule | Backend source |
|---|---|---|
| **Screen** | Exactly one at a time. Native decides every navigation; React only renders what native pushes. | `web/src/App.tsx:58-60`, `Services/ReactNavigationService.cs:339-383` |
| **Overlay** | At most one at a time; a new overlay replaces the current one. Does not change the screen underneath. | `ReactNavigationService.cs:131-160`, `web/src/bridge/contract.ts:809-817` |
| **Close prompt** | Cancel-migration confirm / desktop-shortcut prompt. Renders above any overlay. | `App.tsx:230-251` |

State kinds used below:

- **user** — waits for a user action.
- **waiting** — the engine moves the app on; the runner only waits (and handles overlays).
- **peer** — waits on the Source PC; the runner must sync through the coordination service.
- **terminal** — only exit is closing the app.

Triggers are written as `action:` (a click/type the runner performs) or `event:` (an engine
message or OS event the runner only waits for). Bridge channel names are given so a future
log-based observer can match them; React also reports every view/modal change to the native
log as `diagnostics.view` / `diagnostics.modal`.

Detection column = today's assertion module (text-based) and the React screen/overlay id
(log-based alternative).

## 2. Screen transitions

### `welcome` — kind: user

Variants depend on sign-in state and SupportAssist entitlement
(`WelcomeFamilyStage.tsx:54-104`, `WelcomePageViewModel.cs:200-210`). `IsFirstLaunch` is
hard-coded `true`, so the "returning user, not signed in" variant never shows **[inferred]**.

| Trigger | To | Notes / source |
|---|---|---|
| action: Continue (`welcome.continue`), signed in | `checkPrerequisites` | Engine launch first; skips relaunch if Init.CDM already acked. `WelcomePageViewModel.cs:263-313` |
| action: Continue, not signed in | overlay `signIn` | Browser opens automatically. `SignInPageViewModel.cs:141-150` |
| action: Continue, signed in, **not entitled** | `welcome` (no change) | Dead end by design. `WelcomePageViewModel.cs:200-203` |
| action: Remind me later (`welcome.remindLater`) | `welcomeDeferral` | `:223-228` |
| action: Sign out (`window.signOut`) | overlay `signOut` | `MainWindowViewModel.cs:330-492` |
| event: engine launch fails | overlay `failure` (Close) | `Services/EngineLauncher.cs:59-124` |

Detection: `assertions/target/welcome_screen.py` (Continue button), `welcome_back_screen.py`; log id `welcome`.

### `welcomeDeferral` / `welcomeDeferralError` / `deferralSuccess` — kind: user

| From | Trigger | To | Source |
|---|---|---|---|
| `welcomeDeferral` | action: Set reminder (`welcomeDeferral.setReminder {tonight\|tomorrow\|nextWeek}`), schedule OK | `deferralSuccess` | `WelcomeDeferralPageViewModel.cs:73-103` |
| `welcomeDeferral` | action: Set reminder, schedule fails | `welcomeDeferralError` | same |
| `welcomeDeferral` | action: Close (`welcomeDeferral.close`) | `welcome` | `:105-109` |
| `welcomeDeferralError` | action: Close (reuses `welcomeDeferral.close`) | `welcome` | `WelcomeDeferralErrorScreenAdapter.cs:49-52` |
| `deferralSuccess` | action: Close (`deferralSuccess.close`) | `welcome` | `DeferralSuccessPageViewModel.cs:69-73` |

Detection: no assertions exist yet. Headings: `WelcomeDeferral_PickerTitle`, `WelcomeDeferralSuccess_Title` ("Got it"), `WelcomeDeferralError_Title`.

### `checkPrerequisites` — kind: waiting

Two phases: waiting for the engine's Init.CDM (**no timeout [inferred]**,
`CheckPrerequisitesPageViewModel.cs:114-130`), then PreCheck.Migration + Network.Get
(`:146-165`). First failing precheck wins, in this order (`PrecheckEvaluator.cs:83-123`):
OS (bypassed) → admin → battery → network → locale → public network → running apps → ready.

| Trigger | To | Source |
|---|---|---|
| event: precheck Ready, not paired | `connectOldPc` | `:217-245` |
| event: precheck Ready, already paired | `readyToMove` | `:261-266` |
| event: TrustRequired (public network) | overlay `trustNetwork` | `:217-245` |
| event: not admin | overlay `notAdmin` | `PrecheckFailureRoute.cs` |
| event: battery failed | overlay `batteryCritical` | same |
| event: network failed | overlay `noNetwork` (ThisPcPrecheck) | same |
| event: locale unsupported | overlay `localeNotSupported` | `PrecheckFailureRoute.cs:65-67` |
| event: apps running | overlay `closeApplications` | same |
| event: Blocked | overlay `failure` (Close) | same |
| event: single engine error, Status=false | `checkPrerequisites` (reload) | `MainWindowViewModel.cs:578-579` |
| action: Cancel (`checkPrerequisites.cancel`) | `welcome` | Stop → wait for ack → reset. `:269-286` |

Detection: `assertions/target/migration_preparation_transition.py` (page-source phrases); log id `checkPrerequisites`.

### `connectOldPc` — kind: peer (Source must be searching on the same network)

Sends Pairing.Init on entry; if already paired skips to `readyToMove`
(`ConnectOldPcPageViewModel.cs:97-113`). No Continue button.

| Trigger | To | Source |
|---|---|---|
| event: Pairing.VerificationCodeRequest | `enterCode` | `:151-174` |
| event: Network.TrustResponse FailureCode ≠ 0 | overlay `trustNetwork` | `:177-194` |
| event: Pairing.Confirmation 2500 (no device after **10 min**, repeatable) | inline modal `NoDeviceFoundModal` | `:236-245`, `PairingEvaluator.cs:75-77` |
| action: NoDeviceFound → Cancel transfer (`connectOldPc.goToWelcome`) | `welcome` | Stop first. `NoDeviceFoundModal.tsx` |
| event: 2497 / 2502 (restart required) | `connectOldPc` (reload; hides noNetwork/trustNetwork) | `:247-266` |
| event: 2701 / 2702 (version mismatch) | overlay `failure` (version-mismatch copy, "Cancel transfer") | `:221-231`, `VersionMismatchRoute.cs:52-65` |
| event: OS network drop | overlay `noNetwork` (ThisPcPairing) | `MainWindowViewModel.cs:1001-1019` |
| action: Cancel (`connectOldPc.goToWelcome`) | `welcome` | Stop → ack. `:130-148` |

Detection: `assertions/target/pairing_discovery_screen.py`; log id `connectOldPc`.

### `enterCode` — kind: peer (Source publishes the code)

Typing auto-links once the code is complete (`EnterCodeStage.tsx`, `EnterCodePageViewModel.cs:162`).

| Trigger | To | Source |
|---|---|---|
| action: type full code (`enterCode.setCode` → `enterCode.link`) | waits for Pairing.Confirmation | — |
| event: Paired | `readyToMove` after a **1 s** success state | `EnterCodePageViewModel.cs:353-402` |
| event: wrong code, attempts < 3 | `enterCode` (code cleared, retry message) | `PairingEvaluator.cs:95-135` |
| event: wrong code, attempts ≥ 3 | `enterCode` **locked** (read-only, mm:ss countdown from engine `RetryDelayInSeconds`, unlocks at 0) | `:436-488` |
| event: 2500 | inline modal `NoDeviceFoundModal` → Cancel transfer → `welcome` | `enterCode.goToWelcome` |
| event: 2497 / 2502 | `connectOldPc` | `:311-427` |
| event: 2701 / 2702 | overlay `failure` (version mismatch) | same |
| event: OS network drop | overlay `noNetwork` (ThisPcPairing) | `MainWindowViewModel.cs:1001-1019` |
| action: Cancel (`enterCode.cancel`) | `welcome` | Stop → ack. `:202-220` |

Detection: `assertions/target/pairing_code_entry_screen.py`; log id `enterCode`. The locked
state has no assertion yet (status text `EnterCode_StatusLocked`).

### `readyToMove` — kind: waiting

Runs Compatibility.Migration once, in this order: locale → profile → overall status
(`ReadyToMovePageViewModel.cs:118-147, 300-379`). Must **not** re-run PreCheck.Migration
(`:51-57`). No gather timeout in the UI.

| Trigger | To | Source |
|---|---|---|
| event: info already gathered | `chooseWhatToMove` | `:118-147` |
| event: locale incompatible | overlay `localeMismatch` (terminal) | `:300-339` |
| event: profile mismatch | overlay `accountMismatch` | same |
| event: hard incompatible | overlay `failure` (Close) | same |
| event: MigrationInfo.Details | `chooseWhatToMove` | `:346-379` |
| event: Error.Details 2601 / 2607 / 2600 | overlay `failure` (Close) | `EngineErrorRoute.cs:108-157` |
| action: Cancel (`readyToMove.cancel`) | `welcome` | Code goes to Welcome; the React/contract comments say "exits the app" — **code wins**. `:266-284` |

Detection: `assertions/target/transfer_receive_screen.py` covers the *next* screen only; no assertion for this screen yet (heading `ReadyToMove_Title`). Log id `readyToMove`.

### `chooseWhatToMove` — kind: user

Mode "everything" is the default on every fresh visit (`ChooseWhatToMovePageViewModel.cs:685`).
Migrate now is enabled only when: selection fits, estimate current, chain not running,
something selected, tree not loading (`:333-337`, `ChooseWhatToMoveStage.tsx:87`).

| Trigger | To | Source |
|---|---|---|
| action: Let me choose (`setEntryChoice {moveEverything:false}`) | `chooseWhatToMove` (tree mode) | `:356-376` |
| action: Go back | `chooseWhatToMove` (everything; reselects all) | same |
| action: tree `setAllSelected` / `setNodeSelected` / `expandNode` | same screen; estimate recalculates (**20 s** timeout) | `:209` |
| action: drive row Change (`openDriveMappingModal`) | inline modal DriveMapping | `:1454-1509` |
| action: DriveMapping Rescan (`rescan`, **120 s** timeout) / Apply (`applyDriveMapping`, only after a change) / Cancel | `chooseWhatToMove` | `:217` |
| state: selection does not fit | Migrate card red, button disabled; per-drive shortfall text | `ChooseWhatToMoveStage.tsx:73-75` |
| action: Migrate now (`chooseWhatToMoveMigrateNow`) → chain step 1 InstallApplications, browsers missing | overlay `installBrowser` | `MigrateNowChain.cs`, `:1637-1783` |
| chain step 2 ExtendedPreCheck, apps must close | overlay `closeApplications` (chain mode) | same |
| chain step 1/2 fails with nothing to show | `chooseWhatToMove` + inline "couldn't get everything ready" | same |
| chain step 4 Migration.Start | `migrating` (navigates **before** sending Start) | `:1839-1858` |
| event: Error.Details 2206 (old PC cancelled) before Start | overlay `migrationCancelled` | `MainWindowViewModel.cs:1279-1281` |
| action: Cancel (`chooseWhatToMove.cancel`) | `welcome` | Stop → full session reset. `:1419-1432` |

Detection: `assertions/target/transfer_receive_screen.py` ("ready to transfer your files", everything mode only); the tree mode heading is `ChooseWhatToMove_Title`. Log id `chooseWhatToMove`.

### `migrating` — kind: waiting (peer: Source must be transferring)

| Trigger | To | Source |
|---|---|---|
| action: Cancel link | React-only `CancelMigrationConfirmModal` (not an overlay) | `MigratingStage.tsx:45-49, 89-97` |
| action: confirm → "Yes, cancel" (`migrating.cancel`) | "Stopping" state → `resultsSummary` (CancelledLocally) on Cancel ack or **10 s** timeout | `MigratingPageViewModel.cs:113, 437-523` |
| action: confirm → "No, continue" | `migrating` | modal dismissed |
| event: migration finishes while confirm modal is up | modal closes itself | `MigratingStage.tsx:45-49` |
| event: CompleteOnTarget | `resultsSummary` (Completed) | `:537-576` |
| event: Error.Details 2206 after Start | `resultsSummary` (CancelledByOldPc) | same |
| event: Network.Status 2505 / OS drop | overlay `noNetwork` (ThisPcPostPairing) — **auto-recovers** | `MainWindowViewModel.cs:840-851` |
| event: Network.Status 2506 | overlay `noNetwork` (OtherPcPostPairing) — **auto-recovers** | same |
| event: window X / Alt+F4 | close prompt `CancelMigrationConfirm` | `AppCloseCoordinator.cs:100-141` |

File progress tops out at 99% until completion (`:43-45`). Detection:
`assertions/target/transfer_progress_screen.py`; log id `migrating`.

### `resultsSummary` — kind: user (after a loading phase)

Loading sends Migration.Report; **150 s** timeout shows "unavailable" tiles
(`ResultsSummaryPageViewModel.cs:120`).

| Trigger | To | Source |
|---|---|---|
| action: View the details, something skipped (`resultsSummary.showSkippedFiles`) | `skippedFiles` | `:456` |
| action: View the details, nothing skipped (`resultsSummary.viewDetails`) | `complete` | `:441` |
| action: Finish (`resultsSummary.finish`), network lost after migration **and** failures exist/unknown | `welcome` | Stop first. `:496-509` |
| action: Finish, no failures / unknown / Stop already sent | `migrationDone` | Stop → ack first |
| action: Finish, failures exist | `migrationDone` | directly |
| event: 2206 while on a results screen | overlay `noNetwork` (OtherPcPostPairing) | `MainWindowViewModel.cs:1258-1270` |

Detection: `assertions/target/migration_summary_screen.py`; log id `resultsSummary`.

### `complete` — kind: user

| Trigger | To | Source |
|---|---|---|
| action: Open a PDF report (`complete.openPdf`; inert until the report is ready) | `complete` | — |
| action: Back to summary (`complete.viewSummary`) | `resultsSummary` | `CompletePageViewModel.cs:221` |

Detection: none yet (heading `Complete_Title` = "Your transfer is complete", same text as the summary heading — **use the "Back to summary" button to tell them apart**). Log id `complete`.

### `skippedFiles` — kind: user

Sends Migration.DetailedReport; tree is checkable. Right-hand card depends on state
(`SkippedFilesView.tsx`, `SkippedFilesPageViewModel.cs:170`, `RetryPolicy.cs`):

| Trigger | To | Source |
|---|---|---|
| action: Retry (allowed if old PC did not cancel and Stop not yet sent; ≥ 1 item checked) | `migrating` (Migration.Start, Retry=true; navigates before sending) | `:517` |
| action: Finish / Go to summary, normal | `migrationDone` | `:564` |
| action: Finish, network lost after migration (`skippedFiles.goHome`) | `welcome` | Stop first |

Retry is blocked, in priority order: old PC cancelled > peer lost > session stopped > already finishing > nothing selected. Detection: none yet (heading `SkippedFiles_Title`). Log id `skippedFiles`.

### `migrationDone` — kind: user

| Trigger | To | Source |
|---|---|---|
| action: View transfer summary (`migrationDone.viewSummary`) | `resultsSummary` | `MigrationDonePageViewModel.cs:158` |
| action: Tell us how we did | React `FeedbackModal`; Submit (`migrationDone.submitFeedback`) or Cancel | stays on screen |
| action: Transfer more data (`migrationDone.migrateMoreData`) | `welcome` | Stop → ack → session restart. `:186-217` |
| action: Erase your old PC (`migrationDone.learnAboutErase`) | `learnAboutErase` | `:170` |
| action: download a PDF (`migrationDone.openPdf`) | `migrationDone` | — |
| action: Close (`migrationDone.close`) | app close flow (may show `DesktopShortcutModal`) | `:95` |

`migrationDone.backToHome` is registered natively but **no React control sends it**.
Detection: `assertions/target/migration_complete_screen.py`; log id `migrationDone`.

### `learnAboutErase` — kind: user

| Trigger | To | Source |
|---|---|---|
| action: Back to Home (`learnAboutErase.backToHome`) | `welcome` | delegates to Migration Done's Back to Home: Stop → ack |
| action: Learn more online / Terms and conditions | external browser (`window.open`) | — |

Detection: none yet (heading `LearnAboutErase_Title`). Log id `learnAboutErase`.

### `migrateReminder` / `migrateReminderSet` — unreachable

Only reachable through `App.TryDebugNavigate` (`App.xaml.cs:571-585`), and nothing sets
`DebugNavScreen` anywhere in the tree **[inferred from grep]**. Excluded from the model.

## 3. Overlay transitions

Columns: trigger, phases it can appear in, each button and where it leads, whether the
app recovers on its own, and the **default runner policy** proposed for the happy path.

| Overlay | Raised by | Phases | Button → To | Auto-recovers | Default policy |
|---|---|---|---|---|---|
| `signIn` (`SignInPageViewModel`) | Continue while signed out | welcome | Waiting view: Retry link (`signIn.retry`), Cancel (`signIn.dismiss`) → hide. Launching: none. Error: Cancel / Retry. Success → engine launch → `checkPrerequisites` (`:367-390`); success but not entitled → hide, stay on `welcome` (`:275-282`) | — | drive the browser sign-in (existing `SignInFlow`) |
| `signOut` | Sign out link | welcome | Success → hide → `welcome` signed-out. Failure → Cancel / Retry. **120 s** redirect timeout = success (`App.config:42`) | — | wait for `welcome` signed-out |
| `trustNetwork` (`TrustNetworkPageViewModel.cs:115-285`) | precheck TrustRequired; TrustResponse ≠ 0; still Public after re-check | before pairing | Trust network (`Network.Trust`) → hide → precheck re-runs → `connectOldPc` (or `readyToMove` if paired); still Public → reshown with message; Cancel → Stop → `welcome`; 2497/2502 → `connectOldPc` | no | click Trust network |
| `closeApplications`, normal (`CloseApplicationsPageViewModel.cs`) | precheck apps running; chain step 2 | before pairing; chooseWhatToMove | Close applications → PreCheck.CloseApplications → success: precheck case re-checks, chain case continues to Start. **Cancel transfer → hide only, no Stop** (`:264-269`; React comment claims "restart from Welcome" — code does not) | no | click Close applications |
| `closeApplications`, failed attempt (`hasFailedAttempt`) | close attempt failed (`:226-231`); **[inferred]** only reachable in the precheck case | before pairing | Retry → send again; Check again → hide → `checkPrerequisites` / `readyToMove` (`:243-254`) | no | click Retry (max N), then fail |
| `installBrowser` (`InstallBrowserPageViewModel.cs:98-115`) | InstallApplicationsResponse lists missing browsers | chooseWhatToMove | Resume → re-check; Skip → drop those bookmark settings, continue; × → reset chain, stay | no | click Skip |
| `accountMismatch` (`AccountMismatchPageViewModel.cs:178-239`) | compatibility profile mismatch | readyToMove | Continue (enabled only if an old-PC account exists) → hide → `chooseWhatToMove` / resume gathering; Cancel transfer → Stop → session restart → `welcome` | no | click Continue |
| `notAdmin` (`NotAdminPageViewModel.cs:65-70`) | precheck not admin | before pairing | Cancel transfer → hide → `welcome` (app stays open) | no | fail run (environment) |
| `osNotSupported` | **never** — OS check bypassed (`PrecheckEvaluator.cs:167-170`) | — | Cancel transfer → `welcome` | — | excluded |
| `batteryCritical` (`BatteryCriticalPageViewModel.cs:52, 93-174`) | precheck battery failed | before pairing | Cancel transfer → Stop → `welcome` | **yes**: AC poll every 3 s → hide → `checkPrerequisites` / `readyToMove` | **wait for it to clear** (today's handler clicks Cancel transfer — change) |
| `noNetwork` ThisPcPrecheck (`NoNetworkPageViewModel.cs`) | precheck network failed | before pairing | Cancel transfer → Stop → `welcome` | **yes**: 3 s OS poll → re-runs the check | wait for it to clear |
| `noNetwork` ThisPcPairing | OS drop on connectOldPc / enterCode / trustNetwork (`MainWindowViewModel.cs:1001-1019`) | pairing | Cancel transfer → Stop → `welcome` | **yes**: engine RestartRequired → `connectOldPc` (`:199-220`) | wait; expect `connectOldPc` |
| `noNetwork` ThisPcPostPairing | Network.Status / Error 2505; OS drop while paired | after pairing | Cancel transfer → Stop → `welcome` | **yes**: Network.Status 2507 → hide, resume page (`MainWindowViewModel.cs:840-851`) | **wait for it to clear** (today's handler clicks Cancel transfer — change) |
| `noNetwork` OtherPcPostPairing | Network.Status / Error 2506; 2206 on a results screen | after pairing | Cancel transfer: results screens → hide + latch "peer lost"; otherwise Stop → `welcome` | **yes**: 2507 | **wait for it to clear** (today's handler aborts the run — change) |
| `noNetwork` AuthSignIn / AuthSignOut | NoInternet during sign-in / sign-out | welcome | Cancel transfer → hide only | **yes**: 3 s poll → retries sign-in / sign-out | wait |
| `connectionLost` (`ConnectionLostPageViewModel.cs:46-72`) | **only** two consecutive errors on the engine channel (`ErrorEscalationPolicy.cs:47-65`) | any | Try again → hide → `enterCode` (before pairing) / `readyToMove` (after); Cancel transfer → app close flow | no | click Try again once, then fail |
| `migrationCancelled` (`PairingRestarter.cs:70, 147-186`) | Error.Details 2206 **before** Migration.Start | pairing → chooseWhatToMove | Try again → session reset + PreCheck.FirewallApplications → `connectOldPc`; no response in **15 s** → `failure` | no | scenario-specific |
| `localeNotSupported` | precheck locale not on the supported list | before pairing | Close → app close flow | no | terminal: fail run |
| `localeMismatch` | compatibility locale incompatible | readyToMove | Close → app close flow | no | terminal: fail run |
| `failure`, not dismissible | Error.Details (2482, 2601, 2607/2600, 2606, 2952, 2609, 2497, 2468, other); envelope error after pairing; engine socket closed; precheck Blocked; hard incompatible; engine launch failure; auth DNS/TLS/proxy; shortcut creation failed; firewall timeout; unhandled exception | any | Close → app close flow. Version mismatch (2701/2702): own title, button reads "Cancel transfer", same action | no | terminal: read body text, fail run |
| `failure`, dismissible (2207 erase started on old PC) (`MainWindowViewModel.cs:1287-1302, 1342-1367`) | Error.Details 2207 | any | Ok → Stop → `welcome` (no transfer yet) / results screen (transfer started; Retry hidden) | no | scenario-specific |

## 4. Close prompts (above everything)

| Prompt | Raised by | Button → To | Source |
|---|---|---|---|
| `CancelMigrationConfirm` | window X / Alt+F4 / `window.close` while Start sent, not ended, no Cancel sent | Cancel migration → shortcut prompt or close; Continue migration → dismiss; dismisses itself if the run ends | `AppCloseCoordinator.cs:100-141`, `CloseFlowResolver` |
| `DesktopShortcutModal` | any close request when no launcher shortcut is on the Desktop **and** not yet answered this session | Create shortcut → create, then close (creation failure → `failure`, no close); No, thanks → close | `ShortcutConsentHelper.cs` |

Window close sequence depends on engine state (`CloseActionResolver.cs:44-66`): not started
→ shut down; starting → wait then Terminate; connected → Stop then Terminate; migrating →
Cancel, Stop, Terminate. Before React has painted, close skips every prompt
(`MainWindow.xaml.cs:588-592`).

## 5. Timeouts the runner must respect

| Wait | Value | Source |
|---|---|---|
| Splash → welcome; Init.CDM; Migration.Stop ack | none **[inferred]** | — |
| Battery / noNetwork (precheck, auth) poll | 3 s | `BatteryCriticalPageViewModel.cs:52`, `NoNetworkPageViewModel.cs:56` |
| Header network/battery poll | 60 s | `MainWindowViewModel.cs:88, 882-903` |
| Pairing success → readyToMove | 1 s | `EnterCodePageViewModel.cs:389` |
| No device found | 10 min, repeatable | `PairingEvaluator.cs:75-77` |
| Wrong-code lockout | after 3rd attempt; engine-supplied delay | `PairingEvaluator.cs:93` |
| Estimate recalculation / drive rescan | 20 s / 120 s | `ChooseWhatToMovePageViewModel.cs:209, 217` |
| Migration.Cancel ack | 10 s, then proceeds anyway | `MigratingPageViewModel.cs:113` |
| Migration.Report | 150 s, then "unavailable" tiles | `ResultsSummaryPageViewModel.cs:120` |
| Firewall re-provision (migrationCancelled → Try again) | 15 s, then `failure` | `PairingRestarter.cs:70` |
| Close sequence: Cancel ack / Terminate / engine connect | 10 / 60 / 30 s | `AppCloseCoordinator.cs:65-67`, `App.config:33-38` |
| Sign-out redirect | 120 s, treated as success | `App.config:42` |

## 6. Peer sync points (Target ↔ Source via the coordination service)

| Target state | Needs from Source | Existing key / mechanism |
|---|---|---|
| `connectOldPc` | Source searching on the same network | none today (Target just waits for `enterCode`) |
| `enterCode` | the 6-digit code | `CoordinationClient.wait_for()` in `TargetPairingFlow` |
| `readyToMove` → `chooseWhatToMove` | Source past "successfully linked" and gathering | implicit |
| `migrating` | Source in "migrating your data now" | implicit |
| `resultsSummary` | Source finished / cancelled | implicit |
| scenario "old PC cancels" | Source clicks Cancel at an agreed point | **new key needed** (e.g. `source_cancel_at`) |

## 7. What changes versus today's `flows/target/`

1. **Three handlers currently abort or cancel where the app recovers on its own**:
   `noNetwork` (this PC, post-pairing), `noNetwork` (other PC), `batteryCritical`. Policy
   should be "wait for the overlay to clear", with a scenario-level cap.
2. **`closeApplications` failed state** has different buttons (Retry / Check again); the
   component only knows "Close applications".
3. **`connectionLost`** is not handled at all (rare: needs two consecutive engine errors).
4. **Screens with no assertion yet**: `readyToMove`, `complete`, `skippedFiles`,
   `learnAboutErase`, the deferral family, `enterCode` locked state, the
   `chooseWhatToMove` tree mode.
5. **Same heading, two screens**: `resultsSummary` and `complete` both show "Your transfer
   is complete"; disambiguate by button ("Finish" vs "Back to summary") or by log id.
6. Every Cancel returns to `welcome`, so one run can chain several cancel checks without
   relaunching the app.

## 8. Proposed data shape (for the follow-up implementation)

```yaml
screens:
  enterCode:
    kind: peer
    detect: assertions.target.pairing_code_entry_screen.is_showing
    log_id: enterCode
    actions:
      type_code:  {component: PairingCodeEntryScreen.enter_code, expect: [readyToMove, enterCode]}
      cancel:     {component: PairingCodeEntryScreen.click_cancel, expect: [welcome]}
    events:
      paired:            {to: readyToMove, within: 30}
      restart_required:  {to: connectOldPc}
      version_mismatch:  {to_overlay: failure}
    overlays_possible: [noNetwork, failure, connectionLost]

overlays:
  noNetwork:
    detect: assertions.target.network_disconnected_dialog.is_showing
    actions:
      cancel_transfer: {component: NetworkDisconnectedDialog.click_cancel_transfer, expect: [welcome]}
    auto_recovers: true
    default_policy: wait_until_gone   # cap set per scenario
```

## 9. Open items to confirm on a live run before this becomes code

- Whether the Target native log is readable from the automation process, and its format,
  so the observer can use `diagnostics.view` / `diagnostics.modal` instead of heading text.
- Escape-key behaviour on `PopUpModel`: two comments in the React code disagree
  (`PopUpModel.tsx:60-70` vs `DesktopShortcutModal.tsx:12-13`).
- The `closeApplications` failed state: whether it is reachable only in the precheck case.
- Whether `readyToMove` Cancel really lands on `welcome` (code) rather than exiting (comments).

## 10. Code-vs-comment mismatches to raise with the rebit team

- `readyToMove` Cancel: code → Welcome; comments say app exit.
- `closeApplications` Cancel transfer: code hides the overlay only; comment says restart
  from Welcome. In the precheck case this can leave the user on the Check Prerequisites
  spinner with only Cancel available **[inferred]**.
- `migrationDone.backToHome` and `migrateReminderSet.startMigrationNow` are registered
  natively but no React control sends them.
- `IsFirstLaunch` is hard-coded `true`.
- OS-not-supported check is bypassed, so that overlay can never appear.
