# Full transfer -- end-to-end flow, traced from the code

Every diagram below is a direct translation of one method's actual control flow (loops,
branches, retries, exact function names) -- not a paraphrase. Each diagram is labeled
with the exact file and method it maps to, so you can open that file side by side and
check it line for line. This is deliberately split into one diagram per method/stage
rather than one giant diagram -- a single graph with every branch in this scenario
would be unreadable.

For a higher-level, less granular view (what's confirmed live vs. not, grouped by
stage) see [TEST_SCENARIOS.md](TEST_SCENARIOS.md). For the dialog catalog referenced
throughout (exact heading text, scope, fatal vs. non-fatal) see
[DIALOG_HANDLING.md](DIALOG_HANDLING.md).

**Color key** used in every diagram: <span style="color:#c0392b">red = fatal (raises,
ends the run)</span>, <span style="color:#b8860b">amber = recoverable dialog (clicked
through, loop continues)</span>, <span style="color:#2e7d32">green = the real success
exit of that diagram</span>.

## Contents

1. [Orchestration dispatch](#1-orchestration-dispatch) -- `orchestration/role_runner.py`
2. Target -- `SignInFlow`:
   - [2a. `run()` top level](#2a-signinflowrun-top-level) -- `flows/target/authentication/sign_in_flow.py`
   - [2b. `_click_sign_in_with_retry()`](#2b-_click_sign_in_with_retry)
   - [2c. `_run_fresh_auth_with_retry()`](#2c-_run_fresh_auth_with_retry)
   - [2d. `_wait_for_trust_network_then_pairing_discovery()`](#2d-_wait_for_trust_network_then_pairing_discovery-shared-loop) (shared loop, called from 3 places in 2a/2c)
   - [2e. `wait_for_source_pc()`](#2e-wait_for_source_pc) -- called separately by `role_runner.py`, after `run()` returns
3. [Target -- `TargetPairingFlow`](#3-target-targetpairingflow) -- `flows/target/pairing_flow.py`
4. Target -- `TargetTransferFlow` -- `flows/target/transfer_flow.py`:
   - [4a. `start_transfer()`](#4a-start_transfer)
   - [4b. `wait_for_completion()`](#4b-wait_for_completion)
5. [Source -- `SourcePairingFlow`](#5-source-sourcepairingflow) -- `flows/source/pairing_flow.py`
6. [Source -- `SourceTransferFlow`](#6-source-sourcetransferflow) -- `flows/source/transfer_flow.py`

---

## 1. Orchestration dispatch

`orchestration/role_runner.py` -- `SCENARIOS["full_transfer"]` -> `RoleRunner.run()`

```mermaid
flowchart TD
    CLI["python -m orchestration.role_runner<br/>--role --run-id --scenario full_transfer"] --> RoleCheck{"role?"}
    RoleCheck -->|target| TPrefix["TargetRunner.run():<br/>SignInFlow.run()<br/>+ wait_for_source_pc()<br/>+ TargetPairingFlow.enter_pairing_code_from_coordination_service()"]
    RoleCheck -->|source| SPrefix["SourceRunner.run():<br/>SourcePairingFlow.run()"]
    TPrefix --> TSteps["full_transfer_target(session):<br/>TargetTransferFlow.start_transfer()<br/>+ wait_for_completion()"]
    SPrefix --> SSteps["full_transfer_source(session):<br/>SourceTransferFlow.wait_for_transfer_to_start()<br/>+ wait_for_migration_to_complete()"]
    TSteps --> Cleanup["finally: Session.close()<br/>finally: build_report()"]
    SSteps --> Cleanup
    class Cleanup success
    classDef success fill:#d4edda,stroke:#2e7d32,color:#1b4d1f;
```

---

## 2a. `SignInFlow.run()` -- top level

```mermaid
flowchart TD
    Start(["run() called"]) --> AlreadySignedIn{"_already_signed_in()?<br/>(checks, in order: pairing-discovery showing,<br/>trust-network showing, Welcome-back showing)"}

    AlreadySignedIn -->|"pairing-discovery already showing<br/>(pure pass-through, nothing to click)"| End
    AlreadySignedIn -->|"trust-network already showing<br/>(click Trust Network)"| End
    AlreadySignedIn -->|"Welcome-back shown<br/>(click Get Started,<br/>sets _just_clicked_get_started=True)"| Uac2["_wait_for_uac_approval()"]
    Uac2 --> TND2["_wait_for_trust_network_then_pairing_discovery()<br/>(see 2d)"]
    TND2 --> End

    AlreadySignedIn -->|"False -- no shortcut matched"| Snapshot["snapshot_browser_windows()"]
    Snapshot --> ClickRetry["_click_sign_in_with_retry()<br/>(see 2b)"]
    ClickRetry -->|"opened_browser = True"| FreshAuth["_run_fresh_auth_with_retry()<br/>(see 2c -- this already calls 2d<br/>internally before returning)"]
    ClickRetry -->|"opened_browser = False<br/>(app transitioned directly, no browser)"| Uac1["_wait_for_uac_approval()"]
    Uac1 --> TND1["_wait_for_trust_network_then_pairing_discovery()<br/>(see 2d)"]
    TND1 --> End
    FreshAuth --> End

    End(["SignInFlow complete --<br/>reached pairing-discovery screen"])
    class End success

    AlreadySignedIn -.->|"any BaseException<br/>anywhere in this whole method"| Cleanup
    ClickRetry -.->|"any BaseException"| Cleanup
    FreshAuth -.->|"any BaseException"| Cleanup
    Uac1 -.->|"any BaseException"| Cleanup
    Uac2 -.->|"any BaseException"| Cleanup
    Cleanup["_cleanup_after_failure()<br/>(session.close())"] --> Reraise["re-raise"]
    class Cleanup,Reraise fatal

    classDef success fill:#d4edda,stroke:#2e7d32,color:#1b4d1f;
    classDef fatal fill:#f8d7da,stroke:#c0392b,color:#7a1f1f;
```

## 2b. `_click_sign_in_with_retry()`

Called only when no already-signed-in shortcut matched. Returns whether a fresh
browser window actually opened.

```mermaid
flowchart TD
    Start(["for attempt in 1..3"]) --> ClickBtn["Click Sign In on the Welcome screen"]
    ClickBtn --> Poll{"poll every 0.5s,<br/>up to wait_timeout=45s"}
    Poll --> Alive["_assert_app_alive()"]
    Alive --> Shortcut["Desktop-shortcut dialog showing?<br/>click Create shortcut"]
    Shortcut -->|"handled"| Poll
    Shortcut -->|"not showing"| NewBrowser{"New browser<br/>window found?"}
    NewBrowser -->|"yes"| ReturnTrue(["return True<br/>(opened_browser)"])
    NewBrowser -->|"no"| Transition{"Migration-prep<br/>transition screen<br/>matched?"}
    Transition -->|"yes"| ReturnFalse1(["return False<br/>(already authenticated, no browser)"])
    Transition -->|"no"| TrustNet{"Trust-network<br/>dialog showing?"}
    TrustNet -->|"yes"| ReturnFalse2(["return False"])
    TrustNet -->|"no"| PairDisc{"Pairing-discovery<br/>showing?"}
    PairDisc -->|"yes"| ReturnFalse3(["return False"])
    PairDisc -->|"no"| Poll

    Poll -->|"wait_timeout elapsed,<br/>nothing recognized"| WelcomeGone{"Welcome screen<br/>still showing?"}
    WelcomeGone -->|"gone<br/>(click plausibly worked,<br/>landed somewhere unrecognized)"| ReturnFalse4(["return False"])
    WelcomeGone -->|"still there<br/>(click plausibly did nothing)"| NextAttempt["retry: next attempt"]
    NextAttempt --> ClickBtn
    NextAttempt -.->|"all 3 attempts exhausted"| Raise(["raise SignInError"])

    class ReturnTrue,ReturnFalse1,ReturnFalse2,ReturnFalse3,ReturnFalse4 success
    class Raise fatal
    classDef success fill:#d4edda,stroke:#2e7d32,color:#1b4d1f;
    classDef fatal fill:#f8d7da,stroke:#c0392b,color:#7a1f1f;
```

## 2c. `_run_fresh_auth_with_retry()`

Called only when `_click_sign_in_with_retry()` returned `True` (a real browser
opened). `run_negative_check` is `True` only on the very first attempt (`attempt == 0`)
-- every run deliberately submits a wrong OTP once, by design.

```mermaid
flowchart TD
    Start(["for attempt in 0..MAX_AUTH_RETRIES-1 (3)"]) --> Attach["attach_browser()"]
    Attach --> Restore["Restore-pages dialog showing? click Close"]
    Restore --> Email{"Email field present?"}
    Email -->|"yes"| SubmitEmail["Submit correct username"]
    Email -->|"no -- skip"| Password
    SubmitEmail --> Password{"Password field present?"}
    Password -->|"yes"| Restore2["Restore-pages showing again? click Close"] --> SubmitPwd["Submit correct password"]
    Password -->|"no -- skip"| OTP
    SubmitPwd --> OTP{"OTP boxes present?"}
    OTP -->|"no -- skip"| Uac
    OTP -->|"yes, run_negative_check=True<br/>(attempt 0 only)"| WrongOtp["Submit WRONG OTP on purpose<br/>-> confirm error banner<br/>-> click OTP page's own Cancel"]
    OTP -->|"yes, run_negative_check=False<br/>(attempt 1+)"| RightOtp["Submit correct OTP"]
    WrongOtp --> Uac["_wait_for_uac_prompt_resolution()<br/>(detect consent.exe, wait for manual approval)"]
    RightOtp --> Uac
    Uac --> Outcome["_wait_for_auth_outcome():<br/>races sign-in-failed dialog vs.<br/>transition-screen-match+5s confirm window<br/>-> 'success' / 'failed' / 'timeout'"]
    Outcome --> CloseBrowser["close_browser()"]
    CloseBrowser --> IsSuccess{"outcome?"}
    IsSuccess -->|"success"| TND["_wait_for_trust_network_then_pairing_discovery()<br/>(see 2d)"]
    TND -->|"reached pairing-discovery cleanly"| Done(["return -- SignInFlow.run() continues to 'End'"])
    TND -.->|"_LateSignInFailure raised<br/>(late sign-in-failed dialog)"| Downgrade["outcome := 'failed'"]
    Downgrade --> IsFailed
    IsSuccess -->|"failed"| IsFailed{"outcome == 'failed'?"}
    IsSuccess -->|"timeout"| RaiseTimeout(["raise SignInError"])
    IsFailed -->|"yes"| RetrySignIn["_retry_sign_in():<br/>click Retry on sign-in-failed dialog,<br/>wait for new browser window"]
    RetrySignIn --> Start
    RetrySignIn -.->|"all 3 attempts exhausted"| RaiseExhausted(["raise SignInError"])

    class Done success
    class RaiseTimeout,RaiseExhausted fatal
    classDef success fill:#d4edda,stroke:#2e7d32,color:#1b4d1f;
    classDef fatal fill:#f8d7da,stroke:#c0392b,color:#7a1f1f;
```

## 2d. `_wait_for_trust_network_then_pairing_discovery()` (shared loop)

Called from **three** places: `run()`'s already-signed-in Welcome-back branch, `run()`'s
no-browser branch, and `_run_fresh_auth_with_retry()`'s success path (2a/2c above).

```mermaid
flowchart TD
    Start(["loop while time < deadline"]) --> Alive["_assert_app_alive()"]
    Alive --> SignInFailed{"'We couldn't sign you in'<br/>showing?"}
    SignInFailed -->|"yes"| LateFail(["raise _LateSignInFailure<br/>(an earlier 'success' signal was wrong)"])
    SignInFailed -->|"no"| Regional{"'Set both of your PCs to the<br/>same supported region' showing?"}
    Regional -->|"yes"| RegionalFatal["click Close"] --> RaiseRegional(["raise SignInError"])
    Regional -->|"no"| NetDisc{"'This PC isn't connected<br/>to a network.' showing?"}
    NetDisc -->|"yes"| ClickCheckAgain["click Check again<br/>(after its own 30s wait)"] --> Start
    NetDisc -->|"no"| Battery{"'Plug into AC power' showing?"}
    Battery -->|"yes"| ClickCancelAC["click Cancel transfer<br/>(after its own 15s wait)"] --> Recover["_recover_from_plug_into_ac_power_reset():<br/>confirm Welcome-back screen,<br/>click Get started to re-enter"] --> Start
    Battery -->|"no"| Shortcut["Desktop-shortcut dialog showing?<br/>click Create shortcut"]
    Shortcut -->|"handled"| Start
    Shortcut -->|"not showing"| PairDisc{"Pairing-discovery showing?"}
    PairDisc -->|"yes"| Success1(["return -- success"])
    PairDisc -->|"no"| CodeEntry{"Pairing-code-entry showing?<br/>(app skipped pairing-discovery entirely)"}
    CodeEntry -->|"yes"| Success2(["return -- success"])
    CodeEntry -->|"no"| TrustNet{"Trust-network dialog showing?<br/>(only if not already accepted)"}
    TrustNet -->|"yes"| ClickTrust["click Trust network"] --> Start
    TrustNet -->|"no"| Sleep["sleep 0.5s"] --> Start
    Start -.->|"deadline exceeded"| RaiseTimeout(["raise SignInError"])

    class Success1,Success2 success
    class LateFail,RaiseRegional,RaiseTimeout fatal
    classDef success fill:#d4edda,stroke:#2e7d32,color:#1b4d1f;
    classDef fatal fill:#f8d7da,stroke:#c0392b,color:#7a1f1f;
```

**Known asymmetry, by explicit user direction:** the "Plug into AC power" reset
recovery above (confirm Welcome-back, click Get started) is wired into this loop and
into 2e below, but **not** into `TargetPairingFlow`/`TargetTransferFlow` -- confirmed
to only happen pre-pairing.

## 2e. `wait_for_source_pc()`

Called separately by `orchestration/role_runner.py`'s `TargetRunner.run()`, **after**
`SignInFlow.run()` has already returned successfully.

```mermaid
flowchart TD
    Start(["wait_for_source_pc() called"]) --> Check{"Pairing-discovery<br/>showing?"}
    Check -->|"no"| NothingToWait(["return True --<br/>nothing to wait for"])
    Check -->|"yes"| Loop(["loop while time < deadline (600s default)"])
    Loop --> Alive["_assert_app_alive()"]
    Alive --> NetDisc{"'This PC isn't connected<br/>to a network.' showing?"}
    NetDisc -->|"yes"| ClickCheckAgain["click Check again"] --> Loop
    NetDisc -->|"no"| Battery{"'Plug into AC power' showing?"}
    Battery -->|"yes"| ClickCancelAC["click Cancel transfer"] --> Recover["_recover_from_plug_into_ac_power_reset()"] --> Rerun["re-run _wait_for_trust_network_then_pairing_discovery()<br/>(see 2d) -- NOT a plain continue, since a<br/>plain continue would falsely read 'pairing-discovery<br/>gone' as 'Source found' right after the reset"] --> Loop
    Battery -->|"no"| Shortcut["Desktop-shortcut dialog showing?<br/>click Create shortcut"]
    Shortcut -->|"handled"| Loop
    Shortcut -->|"not showing"| Gone{"Pairing-discovery<br/>NOT showing anymore?"}
    Gone -->|"yes"| Found(["found = True, break -- Source PC found"])
    Gone -->|"no"| Loop
    Loop -.->|"deadline exceeded"| NotFound(["found = False"])
    Found --> Return(["return found"])
    NotFound --> Return
    Return -.->|"False -- caller (TargetRunner.run())<br/>raises RoleRunnerError"| RaiseUp(["RoleRunnerError"])

    class Found,NothingToWait success
    class RaiseUp fatal
    classDef success fill:#d4edda,stroke:#2e7d32,color:#1b4d1f;
    classDef fatal fill:#f8d7da,stroke:#c0392b,color:#7a1f1f;
```

---

## 3. Target -- `TargetPairingFlow`

`enter_pairing_code_from_coordination_service()`, called by `TargetRunner.run()` right
after `wait_for_source_pc()` returns `True`.

```mermaid
flowchart TD
    Start(["enter_pairing_code_from_coordination_service(run_id)"]) --> WaitScreen["_wait_for_screen(screen_timeout=30s):<br/>polls via _poll_with_network_recovery<br/>(see below) for pairing-code-entry showing"]
    WaitScreen -.->|"never appears"| RaiseScreen(["raise PairingError"])
    WaitScreen --> AttemptLoop(["for attempt in 1..3 (max_attempts)"])
    AttemptLoop --> Fetch["coordination_client.wait_for(run_id, pairing_code)<br/>(fetch_timeout=600s)"]
    Fetch --> EnterCode["pairing_code_entry_screen.enter_code(code)"]
    EnterCode --> WaitClear["_poll_with_network_recovery:<br/>wait for pairing-code-entry to CLEAR<br/>(advance_timeout=30s)"]
    WaitClear -.->|"still showing after advance_timeout"| RetryableFail["PairingError / ComponentActionError /<br/>TimeoutError / RuntimeError / RequestException"]
    WaitClear --> AccountCheck{"Account-mismatch confirm<br/>dialog showing? (5s)"}
    AccountCheck -->|"yes"| ClickContinue["click Continue"] --> ReturnSuccess
    AccountCheck -->|"no -- account names matched"| ReturnSuccess(["return -- pairing complete"])
    RetryableFail --> AttemptLoop
    AttemptLoop -.->|"all 3 attempts exhausted"| RaiseLast(["raise last_error"])

    subgraph PWNR["_poll_with_network_recovery(condition, timeout) -- shared by\nboth _wait_for_screen() and the code-clear wait above"]
        direction TD
        PStart(["loop while time < deadline"]) --> PCond{"condition()<br/>true?"}
        PCond -->|"yes"| PSuccess(["return True"])
        PCond -->|"no"| POther{"'The other PC isn't connected<br/>to a network.' showing?"}
        POther -->|"yes"| POtherFatal["click Cancel transfer"] --> PRaiseOther(["raise PairingError"])
        POther -->|"no"| PRegional{"'Set both of your PCs to the<br/>same supported region' showing?"}
        PRegional -->|"yes"| PRegionalFatal["click Close"] --> PRaiseRegional(["raise PairingError"])
        PRegional -->|"no"| PNetDisc{"'This PC isn't connected<br/>to a network.' showing?"}
        PNetDisc -->|"yes"| PClickCheck["click Check again"] --> PStart
        PNetDisc -->|"no"| PBattery{"'Plug into AC power' showing?"}
        PBattery -->|"yes"| PClickCancel["click Cancel transfer<br/>(NOT given the Get-started<br/>reset recovery -- pre-pairing only, see 2d)"] --> PStart
        PBattery -->|"no"| PSleep["sleep(poll_interval=1s)"] --> PStart
        PStart -.->|"deadline exceeded"| PFail(["return False"])
    end

    class ReturnSuccess,PSuccess success
    class RaiseScreen,RaiseLast,PRaiseOther,PRaiseRegional fatal
    classDef success fill:#d4edda,stroke:#2e7d32,color:#1b4d1f;
    classDef fatal fill:#f8d7da,stroke:#c0392b,color:#7a1f1f;
```

---

## 4a. `start_transfer()`

`flows/target/transfer_flow.py`'s `TargetTransferFlow`, called right after
`TargetPairingFlow` returns.

```mermaid
flowchart TD
    Start(["start_transfer(screen_timeout=300s, progress_screen_timeout=30s)"]) --> Outer(["outer loop while time < screen_deadline"])
    Outer --> ME1["_raise_if_migration_error()"]
    ME1 -.->|"'Something went wrong' showing"| FatalME1(["raise TransferFlowError"])
    ME1 --> OPC1["_raise_if_other_pc_disconnected()"]
    OPC1 -.->|"showing -- click Cancel transfer"| FatalOPC1(["raise TransferFlowError"])
    OPC1 --> RS1["_raise_if_regional_settings_not_supported()"]
    RS1 -.->|"showing -- click Close"| FatalRS1(["raise TransferFlowError"])
    RS1 --> AC1{"'Plug into AC power' showing?"}
    AC1 -->|"yes"| ClickAC1["click Cancel<br/>(no Get-started recovery here -- pre-pairing only)"] --> Outer
    AC1 -->|"no"| Ready{"'We're ready to transfer<br/>your files' showing? (0.5s)"}
    Ready -->|"no"| AccountCheck{"Account-mismatch confirm<br/>showing? (only checked once)"}
    AccountCheck -->|"yes, not yet confirmed"| ClickAccounts["click Continue"] --> CloseAppsOuter
    AccountCheck -->|"no / already confirmed"| CloseAppsOuter{"'We need to close all<br/>other applications' showing?"}
    CloseAppsOuter -->|"yes"| ClickCloseOuter["click Close Application"] --> Outer
    CloseAppsOuter -->|"no"| Outer
    Outer -.->|"screen_deadline exceeded"| FatalScreenTimeout(["raise TransferFlowError"])

    Ready -->|"yes"| CloseAppsPre["while 'close other apps' showing:<br/>click Close Application"]
    CloseAppsPre --> ClickMigrate["click 'Bring everything over for me'"]
    ClickMigrate --> Inner(["inner loop while time < progress_deadline"])
    Inner --> ME2["_raise_if_migration_error()"]
    ME2 -.-> FatalME2(["raise TransferFlowError"])
    ME2 --> OPC2["_raise_if_other_pc_disconnected()"]
    OPC2 -.-> FatalOPC2(["raise TransferFlowError"])
    OPC2 --> RS2["_raise_if_regional_settings_not_supported()"]
    RS2 -.-> FatalRS2(["raise TransferFlowError"])
    RS2 --> AC2{"'Plug into AC power' showing?"}
    AC2 -->|"yes"| ClickAC2["click Cancel"] --> Inner
    AC2 -->|"no"| Browsers{"'Want to keep your browser<br/>bookmarks?' showing?"}
    Browsers -->|"yes"| ClickRescan["wait 10s, click Resume once,<br/>re-check, click Skip if still showing"] --> Inner
    Browsers -->|"no"| Moving{"'We're moving your files<br/>and settings' showing? (0.5s)"}
    Moving -->|"yes"| SuccessStart(["return -- transfer confirmed started"])
    Moving -->|"no"| CloseAppsInner{"'close other apps' showing?"}
    CloseAppsInner -->|"yes"| ClickCloseInner["click Close Application"] --> Inner
    CloseAppsInner -->|"no"| Reclick{"time since last click<br/>>= 3s (RECLICK_INTERVAL)?"}
    Reclick -->|"yes"| RecheckMoving{"re-check 'moving files'<br/>(0.3s, right before re-clicking)"}
    RecheckMoving -->|"showing"| SuccessStart
    RecheckMoving -->|"not showing"| ReClickMigrate["re-click 'Bring everything over for me'<br/>(first click may have silently no-opped)"] --> Inner
    Reclick -->|"no"| Inner
    Inner -.->|"progress_deadline exceeded"| FatalProgressTimeout(["raise TransferFlowError"])

    class SuccessStart success
    class FatalME1,FatalOPC1,FatalRS1,FatalScreenTimeout,FatalME2,FatalOPC2,FatalRS2,FatalProgressTimeout fatal
    classDef success fill:#d4edda,stroke:#2e7d32,color:#1b4d1f;
    classDef fatal fill:#f8d7da,stroke:#c0392b,color:#7a1f1f;
```

## 4b. `wait_for_completion()`

Called right after `start_transfer()` returns.

```mermaid
flowchart TD
    Start(["wait_for_completion(transfer_timeout=1800s,<br/>summary_timeout=30s, complete_timeout=30s, home_timeout=30s)"]) --> TLoop(["do-while loop (at least one check)"])
    TLoop --> TME["_raise_if_migration_error()"]
    TME -.-> FatalTME(["raise TransferFlowError"])
    TME --> TOPC["_raise_if_other_pc_disconnected()"]
    TOPC -.-> FatalTOPC(["raise TransferFlowError"])
    TOPC --> TRS["_raise_if_regional_settings_not_supported()"]
    TRS -.-> FatalTRS(["raise TransferFlowError"])
    TRS --> TAC{"'Plug into AC power' showing?"}
    TAC -->|"yes"| TClickAC["click Cancel"] --> TLoop
    TAC -->|"no"| TMoving{"'We're moving your files<br/>and settings' NOT showing? (0.5s)"}
    TMoving -->|"yes -- finished"| Finished["finished = True, break"]
    TMoving -->|"no"| TDeadline{"deadline reached?"}
    TDeadline -->|"yes"| NotFinished["break (finished stays False)"]
    TDeadline -->|"no"| TLoop
    NotFinished -.-> FatalTransferTimeout(["raise TransferFlowError"])
    Finished --> Summary{"'Here's a summary of your<br/>migration results' showing?<br/>(summary_timeout=30s)"}
    Summary -.->|"no"| FatalSummary(["raise TransferFlowError"])
    Summary -->|"yes"| ClickFinish["click Finish"]
    ClickFinish --> Complete{"'Your migration is now<br/>complete' showing?<br/>(complete_timeout=30s)"}
    Complete -.->|"no"| FatalComplete(["raise TransferFlowError"])
    Complete -->|"yes"| ClickPdf["click 'download a PDF'"]
    ClickPdf --> WaitPdf["sleep 5s (PDF_OPEN_WAIT_SECONDS)"]
    WaitPdf --> ClickBack["click 'Back to Home'"]
    ClickBack --> HLoop(["do-while loop: confirm home screen"])
    HLoop --> Shortcut{"Desktop-shortcut dialog showing?"}
    Shortcut -->|"yes"| ClickShortcut["click Create shortcut"] --> HLoop
    Shortcut -->|"no"| SignOut{"'Sign Out' button showing? (0.5s)"}
    SignOut -->|"yes"| HomeConfirmed["home_confirmed = True, break"]
    SignOut -->|"no"| HDeadline{"home_timeout exceeded?"}
    HDeadline -->|"yes"| NotHomeConfirmed["break"]
    HDeadline -->|"no"| HLoop
    NotHomeConfirmed -.-> FatalHome(["raise TransferFlowError"])
    HomeConfirmed --> CloseWindow["click app window's native Close button"]
    CloseWindow --> Done(["Scenario complete"])

    class Done success
    class FatalTME,FatalTOPC,FatalTRS,FatalTransferTimeout,FatalSummary,FatalComplete,FatalHome fatal
    classDef success fill:#d4edda,stroke:#2e7d32,color:#1b4d1f;
    classDef fatal fill:#f8d7da,stroke:#c0392b,color:#7a1f1f;
```

---

## 5. Source -- `SourcePairingFlow`

`flows/source/pairing_flow.py`. **Deadline-extending**: every interrupting dialog
check below pushes the loop's own deadline back by however long it took to handle --
see [DIALOG_HANDLING.md](DIALOG_HANDLING.md)'s cross-cutting notes for why (the
battery-critical dialog in particular is expected to repeat for a long, unpredictable
time).

```mermaid
flowchart TD
    Start(["run(discovery_timeout=600s, pairing_timeout=600s)"]) --> Welcome{"Welcome screen showing? (5s)"}
    Welcome -->|"yes"| ClickGS["click 'Let's get started'"] --> Trust
    Welcome -->|"no -- assume already past it"| Trust{"Trust-network dialog showing? (3s)"}
    Trust -->|"yes"| ClickTrust["click Yes, continue"] --> DLoop
    Trust -->|"no"| DLoop(["discovery loop while time < deadline<br/>(extends on every interrupting check below)"])
    DLoop --> DAlive["_assert_app_alive()"]
    DAlive --> DRegional["raise_if_regional_settings_not_supported()"]
    DRegional -.->|"'Your regional settings aren't<br/>supported.' showing -- click Close"| FatalDRegional(["raise RuntimeError<br/>(app closes itself)"])
    DRegional --> DWelcome{"check_welcome_screen():<br/>'Welcome to Dell Migrate.' reappeared?"}
    DWelcome -->|"yes"| DClickGS2["click Let's get started"] --> DLoop
    DWelcome -->|"no"| DOther{"check_other_pc_disconnected():<br/>'The other PC isn't connected...' showing?"}
    DOther -->|"yes"| DClickCancel["click Cancel transfer<br/>(non-fatal on Source)"] --> DLoop
    DOther -->|"no"| DNetDisc{"'This PC isn't connected<br/>to a network.' showing? (0.1s)"}
    DNetDisc -->|"yes"| DClickCheckAgain["click Check again"] --> DLoop
    DNetDisc -->|"no"| DTrust2{"Trust-network dialog<br/>showing again? (0.1s)"}
    DTrust2 -->|"yes"| DClickTrust2["click Yes, continue"]
    DTrust2 -->|"no"| DBattery
    DClickTrust2 --> DBattery{"check_battery_critically_low():<br/>'Your battery is critically low.' showing?"}
    DBattery -->|"yes"| DBatteryHandle["click Cancel -> dismiss follow-up<br/>'Are you sure you want to cancel?'<br/>via 'No, don't cancel'"] --> DLoop
    DBattery -->|"no"| DCode{"Pairing-code screen<br/>showing? (2s)"}
    DCode -->|"yes"| PublishLoop
    DCode -->|"no"| DSleep["sleep 1.0s"] --> DLoop
    DLoop -.->|"discovery_timeout exceeded"| FatalDiscovery(["raise SourcePairingError"])

    PublishLoop(["_publish_loop(pairing_timeout)<br/>loop while time < deadline (extends same way)"]) --> PAlive["_assert_app_alive()"]
    PAlive --> PRegional["raise_if_regional_settings_not_supported()"]
    PRegional -.-> FatalPRegional(["raise RuntimeError"])
    PRegional --> PWelcome{"check_welcome_screen()?"}
    PWelcome -->|"yes"| PClickGS["click Let's get started"] --> PublishLoop
    PWelcome -->|"no"| POther{"check_other_pc_disconnected()?"}
    POther -->|"yes"| PClickCancel["click Cancel transfer"] --> PublishLoop
    POther -->|"no"| PNetDisc{"network-disconnected showing?"}
    PNetDisc -->|"yes"| PClickCheckAgain["click Check again"] --> PublishLoop
    PNetDisc -->|"no"| PTrust{"trust-network showing?"}
    PTrust -->|"yes"| PClickTrust["click Yes, continue"] --> PublishLoop
    PTrust -->|"no"| PBattery{"check_battery_critically_low()?"}
    PBattery -->|"yes"| PBatteryHandle["click Cancel -> dismiss follow-up confirm"] --> PublishLoop
    PBattery -->|"no"| PCodeGone{"pairing-code screen<br/>NOT showing? (1s)"}
    PCodeGone -->|"yes -- Target has paired"| PDone(["return -- SourcePairingFlow complete"])
    PCodeGone -->|"no"| PReadCode["read_code() (OCR fallback if needed)"]
    PReadCode -.->|"read fails this cycle"| PReadFail["log warning, sleep 5s"] --> PublishLoop
    PReadCode --> PCodeChanged{"code changed since<br/>last publish?"}
    PCodeChanged -->|"yes"| PPublish["coordination_client.publish(run_id, code)"]
    PCodeChanged -->|"no"| PSleep["sleep CODE_REPUBLISH_INTERVAL=5s"] --> PublishLoop
    PPublish -.->|"publish fails this cycle"| PPublishFail["log warning"] --> PSleep
    PPublish --> PSleep
    PublishLoop -.->|"pairing_timeout exceeded"| FatalPairing(["raise SourcePairingError"])

    class PDone success
    class FatalDRegional,FatalDiscovery,FatalPRegional,FatalPairing fatal
    classDef success fill:#d4edda,stroke:#2e7d32,color:#1b4d1f;
    classDef fatal fill:#f8d7da,stroke:#c0392b,color:#7a1f1f;
```

---

## 6. Source -- `SourceTransferFlow`

`flows/source/transfer_flow.py`, called right after `SourcePairingFlow` returns.
`_poll_until_showing()` is a shared helper (same deadline-extending shape as
`SourcePairingFlow`'s loops above) used by both methods below.

```mermaid
flowchart TD
    subgraph PUS["_poll_until_showing(check, timeout) -- shared helper"]
        direction TD
        UStart(["loop while time < deadline (extends per check)"]) --> URegional["raise_if_regional_settings_not_supported()"]
        URegional -.-> UFatalRegional(["raise RuntimeError"])
        URegional --> UWelcome{"check_welcome_screen()?"}
        UWelcome -->|"yes"| UClickGS["click Let's get started"] --> UStart
        UWelcome -->|"no"| UOther{"check_other_pc_disconnected()?"}
        UOther -->|"yes"| UClickCancel["click Cancel transfer"] --> UStart
        UOther -->|"no"| UBattery{"check_battery_critically_low()?"}
        UBattery -->|"yes"| UBatteryHandle["click Cancel -> dismiss follow-up confirm"] --> UStart
        UBattery -->|"no"| UCheck{"check(timeout=1s)<br/>-- the real condition?"}
        UCheck -->|"true"| UReturn(["return True"])
        UCheck -->|"false"| UStart
        UStart -.->|"timeout"| UReturnFalse(["return False"])
    end

    Start(["wait_for_transfer_to_start(screen_timeout=600s,<br/>linked_success_timeout=15s)"]) --> Linked["_poll_until_showing(is_linked_success, 15s)<br/>-- optional, log either way"]
    Linked --> Ready["_poll_until_showing(is_ready_to_migrate, 600s)<br/>-- required"]
    Ready -.->|"False"| FatalReady(["raise RuntimeError"])
    Ready --> StartDone(["wait_for_transfer_to_start() returns"])

    StartDone --> Start2(["wait_for_migration_to_complete(migrating_timeout=60s,<br/>summary_timeout=1800s)"])
    Start2 --> Migrating["_poll_until_showing(is_migrating, 60s) -- required"]
    Migrating -.->|"False"| FatalMigrating(["raise RuntimeError"])
    Migrating --> FLoop(["final-screen loop while time < deadline<br/>(extends per check, same as above)"])
    FLoop --> FRegional["raise_if_regional_settings_not_supported()"]
    FRegional -.-> FFatalRegional(["raise RuntimeError"])
    FRegional --> FWelcome{"check_welcome_screen()?"}
    FWelcome -->|"yes"| FClickGS["click Let's get started"] --> FLoop
    FWelcome -->|"no"| FOther{"check_other_pc_disconnected()?"}
    FOther -->|"yes"| FClickCancel["click Cancel transfer"] --> FLoop
    FOther -->|"no"| FBattery{"check_battery_critically_low()?"}
    FBattery -->|"yes"| FBatteryHandle["click Cancel -> dismiss follow-up confirm"] --> FLoop
    FBattery -->|"no"| FError{"'We ran into a problem during<br/>your migration.' showing? (0.1s)"}
    FError -->|"yes"| FClickTryAgain["click Try Again"] --> FLoop
    FError -->|"no"| FComplete{"full-success screen confirmed?<br/>(heading + body, 1s)"}
    FComplete -->|"yes"| FFull["migration_complete = True<br/>dismiss_action = click_close"]
    FComplete -->|"no"| FPartial1{"partial variant 1 confirmed?<br/>('Your migration is now complete.')"}
    FPartial1 -->|"yes"| FP1["migration_complete = False<br/>dismiss_action = click_close_icon<br/>(no Close button on this variant)"]
    FPartial1 -->|"no"| FPartial2{"partial variant 2 confirmed?<br/>('Your migration summary is ready.')"}
    FPartial2 -->|"yes"| FP2["migration_complete = False<br/>dismiss_action = click_close_after_delay"]
    FPartial2 -->|"no"| FLoop
    FLoop -.->|"summary_timeout exceeded,<br/>none of the 3 ever confirmed"| FatalNone(["raise RuntimeError"])
    FFull --> Dismiss["dismiss_action()"]
    FP1 --> Dismiss
    FP2 --> Dismiss
    Dismiss --> Done(["return migration_complete --<br/>Scenario complete"])

    class UReturn,StartDone,Done success
    class FatalReady,FatalMigrating,UFatalRegional,FFatalRegional,FatalNone fatal
    classDef success fill:#d4edda,stroke:#2e7d32,color:#1b4d1f;
    classDef fatal fill:#f8d7da,stroke:#c0392b,color:#7a1f1f;
```
