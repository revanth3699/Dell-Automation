---
name: signin-flow-testing
description: Use when testing, extending, or debugging the Target PC sign-in + pairing-discovery automation (flows/target/authentication/sign_in_flow.py, flows/target/pairing_flow.py) -- the full positive/negative test plan, screen dependency graph, and confirmed error text live in tools/signin_flow_test_plan.md.
---

# Target PC Sign-In Flow Testing

Before changing or extending `flows/target/authentication/sign_in_flow.py`,
`flows/target/pairing_flow.py`, or any component/locator they depend on under
`components/target/` or `locators/target/`, read
`tools/signin_flow_test_plan.md` first. It is the authoritative, tester-reviewed
reference for this flow: the full screen dependency graph, the positive-path sequence,
the negative-path matrix (confirmed error text per step), which lockout/retry rules
apply where, and a live coverage status table (built vs. gap vs. explicitly excluded).

Key rules that plan encodes, worth repeating here since they're easy to violate by
accident:

- **Never retry a wrong-value submission in place.** Email gets one deliberately-wrong
  attempt before the real value; password and OTP must be single-attempt-only, full
  stop -- both have a confirmed 6-incorrect-attempts account lockout warned about in
  their own error text.
- **The post-OTP transition screen ("...getting things ready" / "Starting the migration
  assistant") is not a reliable success signal by itself.** It can appear even when
  sign-in was cancelled or failed. Always race it against the "There was a problem
  signing in" / "Sign-in failed. Please try again." dialog; on failure, click that
  dialog's own Retry button and repeat the whole Email→Password→OTP sequence, never
  just the OTP step.
- **Don't click any dialog's Cancel button** (the "Sign in to MyDell to continue" wait
  modal, the sign-in-failed dialog, the confirm-accounts dialog) as part of verifying
  the happy/error paths -- these are genuine destructive user choices, deliberately
  excluded from this test plan.
- When a new screen or error state shows up that isn't in the plan yet, update
  `tools/signin_flow_test_plan.md` in the same change -- don't let the code and the
  plan drift apart.
- **If a live run looks stuck or behaves strangely (checks spaced far apart in the log,
  an unexpected screen already showing before automation touched anything), check for
  orphaned processes before assuming a logic bug.** Confirmed live (2026-10-05): a run
  interrupted externally (Ctrl+C, a killed background task) raises `KeyboardInterrupt`,
  which does not inherit from `Exception` -- `run()`'s cleanup-triggering except clause
  must catch `BaseException`, not `Exception`, or interrupted runs silently skip
  `_cleanup_after_failure()` entirely. A leftover Chrome "Sign In | Dell US" window from
  one such interrupted run was mistaken for a current run's progress, wasting real
  debugging time on a problem that didn't exist. `Get-Process -Name msedge,chrome |
  Where-Object { $_.MainWindowTitle -ne "" }` finds specifically-titled stale windows
  safely (safe to close by PID once identified this way -- never blanket-kill
  chrome.exe/msedge.exe, since the user's own unrelated windows share the same process
  name).
