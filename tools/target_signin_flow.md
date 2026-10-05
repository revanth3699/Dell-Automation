# Target PC Sign-In Flow

Current implementation scope: **Target PC only.** Source PC has no authentication step,
confirmed directly during this build -- the flow below lives entirely under
`flows/target/authentication/sign_in_flow.py` and the Page Objects in
`components/target/`. There is no parameterize-by-role version of this flow and there
will not be one.

Legend: solid outline = automated step (implemented and exercised live); diamond =
decision/presence check; dashed outline = manual step requiring a human; dotted gray =
not yet built.

```mermaid
flowchart TD
    Start(["SignInFlow.run() invoked"]) --> ChkPairing

    subgraph Shortcuts["Already-signed-in shortcuts (checked first, every run)"]
        ChkPairing{"Pairing-discovery screen<br/>already showing?"}
        ChkTrust{"Trust-network dialog<br/>already showing?"}
        ChkWelcome{"'Welcome back' screen<br/>already showing?"}
    end

    ChkPairing -- Yes --> Confirmed
    ChkPairing -- No --> ChkTrust
    ChkTrust -- "Yes -- click Trust Network" --> WaitPairing
    ChkTrust -- No --> ChkWelcome
    ChkWelcome -- "Yes -- click blue Get Started button" --> WaitTrust
    ChkWelcome -- No --> ClickSignIn

    subgraph Fresh["Fresh sign-in (browser-driven)"]
        ClickSignIn["Click Sign In on Welcome screen<br/>retry up to 3x, 12s each"]
        AttachBrowser["Attach WinAppDriver session to<br/>external browser window (Chrome / Edge)"]
        DismissRestore["Dismiss 'Restore pages?'<br/>dialog if present"]
        EmailChk{"Email field<br/>present?"}
        EmailSubmit["Type username,<br/>click Continue"]
        PasswordChk{"Password field<br/>present?"}
        PasswordSubmit["Dismiss restore dialog,<br/>type password, click Sign In"]
        OtpChk{"OTP boxes<br/>present?"}
        OtpSubmit["Dismiss restore dialog,<br/>enter 6-digit OTP, click Verify<br/>retry up to 3x"]
        UacManual[/"Manual: approve Windows UAC prompt<br/>(secure desktop -- invisible to automation)"/]
        UacDetect["Poll for 'Starting the migration<br/>assistant' modal (confirms UAC approved)"]
    end

    ClickSignIn --> AttachBrowser --> DismissRestore --> EmailChk
    EmailChk -- Yes --> EmailSubmit --> PasswordChk
    EmailChk -- "No (session cached)" --> PasswordChk
    PasswordChk -- Yes --> PasswordSubmit --> OtpChk
    PasswordChk -- "No (session cached)" --> OtpChk
    OtpChk -- Yes --> OtpSubmit --> UacManual
    OtpChk -- No --> UacManual
    UacManual --> UacDetect --> WaitTrust

    WaitTrust["Wait for + accept<br/>Trust-network dialog"] --> WaitPairing
    WaitPairing["Wait for pairing-discovery screen"] --> Confirmed
    Confirmed(["Confirmed end state:<br/>'We're looking for your other PC'"])
    Confirmed -.-> FutureNode[["Pairing flow -- NOT YET BUILT<br/>waits for Source PC, exchanges code"]]

    classDef terminal fill:#ffffff,stroke:#1c1b1a,stroke-width:2px,color:#1c1b1a;
    classDef decision fill:#ffffff,stroke:#2b2b2b,stroke-width:1.2px,color:#1c1b1a;
    classDef implemented fill:#ffffff,stroke:#2b2b2b,stroke-width:1.2px,color:#1c1b1a;
    classDef manual fill:#ffffff,stroke:#2b2b2b,stroke-width:1.2px,stroke-dasharray:6 4,color:#1c1b1a;
    classDef future fill:#ffffff,stroke:#9a958c,stroke-width:1px,stroke-dasharray:3 3,color:#9a958c;

    class Start,Confirmed terminal
    class ChkPairing,ChkTrust,ChkWelcome,EmailChk,PasswordChk,OtpChk decision
    class ClickSignIn,AttachBrowser,DismissRestore,EmailSubmit,PasswordSubmit,OtpSubmit,UacDetect,WaitTrust,WaitPairing implemented
    class UacManual manual
    class FutureNode future
```

## Notes on confidence

- **Confirmed** -- every automated node (solid outline) has been exercised against the
  live Target PC build, including all three already-signed-in shortcuts.
- **Confirmed** -- root cause of an earlier "Sign In button not found" failure: the
  app's own silent OIDC token refresh (`TrySilentLoginAsync`) can skip the Welcome screen
  entirely -- not a crash, confirmed via the app's own log file.
- **Unconfirmed** -- the "Welcome back" screen's Get Started button locator, and the
  email/password step locators, are inferred from user-supplied screenshots only -- the
  test browser profile has retained an existing session on every live run so far, so
  these exact paths have not yet fired for real.
- **Manual** -- the Windows UAC prompt runs on the secure desktop and is categorically
  invisible to UI Automation/WinAppDriver in any tool (WinAppDriver, Selenium,
  Playwright) -- a human must click Yes. The flow detects approval indirectly via the
  "Starting the migration assistant" modal.
- **Out of scope** -- everything past the pairing-discovery screen (actual pairing with
  Source PC) is not yet built -- blocked on a Coordination Service and real locators for
  the pairing-code screens.

**Source**: `flows/target/authentication/sign_in_flow.py`;
`components/target/sign_in_screen.py`, `common_dialogs.py`, `browser_sign_in_page.py`,
`pairing_discovery_screen.py`; `factory/browser_driver_factory.py`.
