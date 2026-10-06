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
 actions: [pos] submit real email directly → Continue
 (negative check moved to tools/adhoc/ -- see section 6; running it on
 every routine run contributed to a real account lockout, confirmed
 2026-10-06)
 → Password Step

Password Step ("Verify Your Identity")                                     [built]
 depends on: Email Step advanced (field gone)
 actions: [pos] submit real password directly → Sign In
 (negative check moved to tools/adhoc/ -- same reasoning as Email Step)
 → OTP Step

OTP Step ("Two-Step Verification", 6 boxes)                                [built]
 depends on: Password Step advanced (field gone)
 FIRST whole-flow attempt only (run_negative_check=True):
   actions: [neg] submit wrong 6-digit code once → expect error banner
            → click the OTP page's OWN Cancel button (below Verify) --
              NEVER submits the real code in this same pass
   → RACE (see below), which resolves to FAILURE by design
 RETRY attempt(s) (run_negative_check=False):
   actions: [pos] submit real code directly → Verify
   → RACE, expected SUCCESS
 → RACE (see section 3)

RACE: transition screen vs sign-in-failed dialog                           [built]
 ├─ transition screen ("...getting things ready" / "Starting the
 │   migration assistant") → SUCCESS → Trust-Network Dialog
 └─ "There was a problem signing in" / "Sign-in failed. Please
     try again." (Cancel / Retry buttons)        → FAILURE
         → click Retry (still requires a human to approve a REAL
           Windows UAC prompt first, same as the success path) → back
           to Email Step, submitting CORRECT values directly this time
           (no repeated negative checks on email/password either) →
           capped at MAX_AUTH_RETRIES = 3 total

 Confirmed directly by the user (2026-10-06): there is no separate
 "cancel path" distinct from "retry on failure" -- the OTP negative
 check's deliberate Cancel and a genuine failure both resolve through
 this exact same RACE and the exact same Retry button. The first
 whole-flow attempt is EXPECTED to land on FAILURE every run, by design.

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
| 5a | Browser: type WRONG OTP, click Verify, click Cancel (1st attempt only) | Error banner, then sign-in-failed dialog | `OtpStep.submit_and_expect_error()` + `OtpStep.cancel()` |
| 5b | (human) approve UAC → click Retry → repeat 3-5 with correct values | New browser, correct email/password/OTP submitted directly | `_run_fresh_auth_with_retry()`'s 2nd attempt |
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
| Email | wrong email | `"We are unable to match the details you entered with our records"` | **not exercised in the default flow at all** (see below) — confirmed only via `tools/adhoc/test_negative_path_error_messages.py` |
| Password | wrong password | same prefix + `"Your account will be locked if an incorrect password is entered 6 times..."` | **not exercised in the default flow at all** — same adhoc-only script, explicit 6-attempt lockout warning is exactly why |
| OTP | wrong code | same prefix + `"Your account will be locked in case of 6 incorrect attempts."` | exercised on the FIRST whole-flow attempt of every default run (by design, see below); single attempt only — same lockout warning |
| Post-OTP | sign-in cancelled/failed (triggered BY DESIGN every run via OTP's Cancel, or genuinely) | `"There was a problem signing in"` / `"Sign-in failed. Please try again."` | click **Retry** (requires real UAC approval first), repeat whole Email→OTP sequence with correct values, capped at `MAX_AUTH_RETRIES = 3` |
| Pairing code | wrong code | **unconfirmed — no screenshot of this failure state yet** | not automatable until confirmed |

Design rules this plan enforces:
- **Restructured 2026-10-06, after a real account lockout traced to this exact cause**:
  running the wrong-then-right negative check for email AND password on every single
  default run accumulated incorrect attempts across many live runs and tripped the test
  account's confirmed 6-attempt lockout. Email and password now submit the correct value
  directly in the default flow, with NO wrong-value attempt at all — that check moved to
  the dedicated, deliberately-invoked `tools/adhoc/test_negative_path_error_messages.py`
  script (see section 6), run only when specifically re-verifying error-message wording,
  never as part of routine testing.
- **OTP is the one exception, by design, confirmed 2026-10-06**: its wrong-value attempt
  (every default run, first whole-flow attempt only) is followed by clicking Cancel, never
  the correct code in the same pass. This stays in the default flow because it isn't
  purely a negative-path check — it's also how the cancel-and-retry mechanism itself gets
  exercised. The correct code is submitted only on the retry pass that follows, alongside
  correct email/password (no repeated negative checks there either). This means the first
  whole-flow attempt deliberately fails every run -- not a separate "cancel path", the SAME
  retry-on-failure mechanism, exercised on purpose instead of waiting for a genuine failure.

## 4. Automation coverage status

| Area | Status |
|---|---|
| Already-signed-in shortcuts (3 screens) | Built, live-tested |
| "No browser opens" already-authenticated variant | Built, live-tested |
| Email/Password positive (default flow) | Built; correct value submitted directly, no wrong-value attempt (restructured 2026-10-06) |
| Email/Password negative | Built, isolated to `tools/adhoc/test_negative_path_error_messages.py`; not yet re-run live since the restructure |
| OTP positive + negative (default flow) | Built; negative path (wrong code → Cancel) confirmed live, exercised on every default run by design |
| Post-OTP success-vs-failure race + whole-flow retry (now triggered by design, every run, via OTP's Cancel) | Built; every live run today got blocked before completing a full cycle -- once by UAC never appearing, once by a CAPTCHA (likely from today's volume of attempts on one test account). Control-flow logic itself verified via `tools/_test_auth_retry_logic.py` (mock, both outcomes pass). |
| Trust-network dialog | Built, live-tested |
| Pairing-discovery reach + wait-for-source | Built, live-tested |
| Pairing-code entry (positive) | Built; box locators are positional, not confirmed by name |
| Pairing-code entry (negative) | **Gap** — no confirmed error text |
| Confirm-accounts dialog | Built; text/buttons confirmed from diagram, not yet live-tested |
| "Your files are ready to move" onward | Out of scope (next phase) |

## 5. Explicitly excluded from this plan

- Clicking **Cancel** on the Welcome screen's "Sign in to MyDell to continue" modal, the
  sign-in-failed dialog, or the confirm-accounts dialog — these are real, destructive
  user choices (cancel the migration), not something automation should trigger. (The OTP
  page's own Cancel button is the one exception, and is NOT excluded — it's the
  by-design trigger for the negative-path check above, confirmed directly by the user.)
- Source PC's own side of pairing (showing its code) — blocked on Source PC build access.
- Anything past the confirm-accounts dialog (file selection, transfer, completion).

## 6. Adhoc negative-path validation (deliberately invoked only)

`tools/adhoc/test_negative_path_error_messages.py`, added 2026-10-06. Runs the full
wrong-then-right sequence for all three steps in one pass: wrong email → confirm error
banner → correct email → Continue; wrong password → confirm error banner → correct
password → Sign In; wrong OTP → confirm error banner → correct OTP → Verify; then
completes the sign-in normally (trust-network, pairing-discovery) so it doesn't leave the
app in a half-finished state. Same env-var convention and `except BaseException` cleanup
safety net as every other script here.

This exists specifically so the error-message text/locators can still be re-verified on
demand, without that verification living in the default flow where it was burning down
the account's 6-attempt lockout budget on every routine run. Invoke it by hand only when
you specifically need to re-confirm these three banners are still correct — not as part
of normal/routine testing, and not more than once in a short window on the same test
account.
