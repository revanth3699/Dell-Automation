# Target PC Sign-In + Pairing-Discovery Test Plan

Authoritative test design for `flows/target/authentication/sign_in_flow.py` and
`flows/target/pairing_flow.py`. Confirmed sources: live testing (this session, 2026-10-05)
and a user-supplied flow diagram ("dell screens flow.pdf", 2026-10-05, rendered via
poppler and cropped for exact text). Anything not flagged "unconfirmed" below has been
seen live, on screen, during this session.

Scope boundary: starts at app launch, ends at the pairing-code being accepted (and the
optional confirm-accounts dialog). "Your files are ready to move" and everything after it
is a later phase, out of scope here.

## 1. Screen inventory and dependency graph

Each node lists: what must be true to reach it, what the user/automation does on it, and
what it leads to. `[built]` = automated today; `[gap]` = known, not yet automatable (no
confirmed locator/error text); `[excluded]` = deliberately out of scope.

```
Welcome Screen ("Let's make this Dell yours")                              [built]
 ├─ already-signed-in shortcuts checked FIRST, before any click:
 │   ├─ pairing-discovery screen already showing  → passthrough            [built]
 │   ├─ trust-network dialog already showing      → accept, passthrough   [built]
 │   └─ "Welcome back, <name>" screen showing      → click Get Started     [built]
 │        (not a passthrough -- may still gate on UAC transition below)
 └─ else: click Sign In button
     ├─ no browser opens, app has a session under the hood                 [built]
     │    → waits for UAC transition screen, same as below
     │    → NOTE: unconfirmed whether THIS path can also show the
     │      sign-in-failed dialog -- diagram only annotates that
     │      possibility on the browser/OTP path below.            [unconfirmed]
     └─ browser opens → Email Step (below)

Email Step ("Sign In" page, Google Sign In + email field + Continue)       [built]
 depends on: browser attached to the NEW window (snapshot-diffed, not
 "first window found" -- see factory/browser_driver_factory.py)
 actions: [neg] submit wrong email once → expect error banner
          [pos] clear, submit real email → Continue
 → Password Step

Password Step ("Verify Your Identity")                                     [built]
 depends on: Email Step advanced (field gone)
 actions: [neg] submit wrong password once → expect error banner
          [pos] clear, submit real password → Sign In
 → OTP Step

OTP Step ("Two-Step Verification", 6 boxes)                                [built]
 depends on: Password Step advanced (field gone)
 actions: [neg] submit wrong 6-digit code once → expect error banner
          [pos] submit real code → Verify
 → RACE (see section 3)

RACE: transition screen vs sign-in-failed dialog                           [built]
 ├─ transition screen ("...getting things ready" / "Starting the
 │   migration assistant") → SUCCESS → Trust-Network Dialog
 └─ "There was a problem signing in" / "Sign-in failed. Please
     try again." (Cancel / Retry buttons)        → FAILURE
         → click Retry → back to Email Step (whole sequence repeats,
           NOT just OTP) → capped at MAX_AUTH_RETRIES = 3 total

Trust-Network Dialog ("Connect to a trusted network")                      [built]
 depends on: RACE resolved to success, OR an already-signed-in shortcut
 action: click "Trust Network" if shown (optional -- not every run shows it)
 → Pairing-Discovery Screen

Pairing-Discovery Screen ("We're looking for your other PC")               [built]
 depends on: Trust-Network step done (or skipped)
 *** SignInFlow.run()'s confirmed end state stops here. ***
 action: none (passive wait screen) -- clears on its own once Source is found
 → (separate call) SignInFlow.wait_for_source_pc() waits for it to clear   [built]
 → Pairing-Code Entry Screen

Pairing-Code Entry Screen ("Let's connect your two PCs", 6 boxes)          [built]
 depends on: Source PC found (previous screen cleared)
 actions: [pos] enter code (positional box lookup -- names unconfirmed)
          [neg] wrong code → expected error TEXT UNCONFIRMED            [gap]
 → Confirm-Accounts Dialog (conditional) or straight through

Confirm-Accounts Dialog ("Let's make sure we're connecting the
 right user accounts")                                                     [built]
 depends on: pairing code accepted AND the two PCs' account names differ
 (not every run shows this -- confirmed from diagram)
 action: click Continue
 → "Your files are ready to move"                                       [excluded]
```

## 2. Full positive-path sequence (user action → system response → automation)

| # | User/system action | Expected screen/text | Automation call |
|---|---|---|---|
| 1 | App launched | Welcome screen OR an already-signed-in shortcut screen | `SignInFlow._already_signed_in()` |
| 2 | Click Sign In | External browser opens, OR app skips straight to a transition screen | `_click_sign_in_with_retry()` |
| 3 | Browser: type email, click Continue | Email field disappears | `EmailStep.submit()` |
| 4 | Browser: type password, click Sign In | Password field disappears | `PasswordStep.submit()` |
| 5 | Browser: type OTP, click Verify | OTP boxes disappear OR sign-in-failed dialog | `OtpStep.submit()` + `_wait_for_auth_outcome()` |
| 6 | (human) approve Windows UAC prompt | "...getting things ready" / "Starting the migration assistant" | `MigrationPreparationTransition.wait_until_any_showing()` |
| 7 | App shows trust dialog | "Connect to a trusted network" | `TrustNetworkDialog.accept()` |
| 8 | App searches for Source | "We're looking for your other PC" | `PairingDiscoveryScreen.wait_until_showing()` — **`SignInFlow.run()` ends here** |
| 9 | Source PC found | Screen clears | `SignInFlow.wait_for_source_pc()` |
| 10 | App shows pairing-code screen | "Let's connect your two PCs" | `TargetPairingFlow.enter_pairing_code()` |
| 11 | Enter correct code | Screen clears (code accepted) | `PairingCodeEntryScreen.enter_code()` + `wait_until_gone()` |
| 12 | (conditional) account names differ | "Let's make sure we're connecting the right user accounts" | `ConfirmAccountsDialog.accept()` |

## 3. Negative-path matrix

| Step | Wrong input | Expected error text (confirmed) | Retry policy |
|---|---|---|---|
| Email | wrong email | `"We are unable to match the details you entered with our records"` | single attempt only (no lockout risk, but no reason to hammer it either) |
| Password | wrong password | same prefix + `"Your account will be locked if an incorrect password is entered 6 times..."` | **single attempt only** — explicit 6-attempt lockout warning |
| OTP | wrong code | same prefix + `"Your account will be locked in case of 6 incorrect attempts."` | **single attempt only** — same lockout warning |
| Post-OTP | sign-in cancelled/failed | `"There was a problem signing in"` / `"Sign-in failed. Please try again."` | click **Retry**, repeat whole Email→OTP sequence, capped at `MAX_AUTH_RETRIES = 3` |
| Pairing code | wrong code | **unconfirmed — no screenshot of this failure state yet** | not automatable until confirmed |

Design rule this plan enforces: **never retry a wrong-value submission in place.**
Email/password/OTP each get exactly one deliberately-wrong attempt before the real value
is submitted — looping a wrong value would either waste time for no benefit (email) or
burn down the confirmed 6-attempt lockout for no reason (password/OTP). This is why the
negative check is woven into the *same* pass as the positive one, not a separate full run.

## 4. Automation coverage status

| Area | Status |
|---|---|
| Already-signed-in shortcuts (3 screens) | Built, live-tested |
| "No browser opens" already-authenticated variant | Built, live-tested |
| Email/Password/OTP positive + negative | Built; negative paths not yet independently live-tested (browser profile has retained a session on every run so far) |
| Post-OTP success-vs-failure race + whole-flow retry | Built this session; not yet exercised live (hard to trigger a real cancellation on demand) |
| Trust-network dialog | Built, live-tested |
| Pairing-discovery reach + wait-for-source | Built, live-tested |
| Pairing-code entry (positive) | Built; box locators are positional, not confirmed by name |
| Pairing-code entry (negative) | **Gap** — no confirmed error text |
| Confirm-accounts dialog | Built; text/buttons confirmed from diagram, not yet live-tested |
| "Your files are ready to move" onward | Out of scope (next phase) |

## 5. Explicitly excluded from this plan

- Clicking any dialog's **Cancel** button (Welcome screen's "Sign in to MyDell to
  continue" modal, the sign-in-failed dialog, confirm-accounts dialog) — these are
  real, destructive user choices (cancel the migration), not something automation
  should trigger while verifying the happy/error paths a real user takes.
- Source PC's own side of pairing (showing its code) — blocked on Source PC build access.
- Anything past the confirm-accounts dialog (file selection, transfer, completion).
