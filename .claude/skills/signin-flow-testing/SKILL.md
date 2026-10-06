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

- **Email and password get NO wrong-value attempt in the default flow at all, as of
  2026-10-06.** They used to get one deliberately-wrong attempt before the real value,
  but running that on every single default run accumulated enough incorrect attempts
  across repeated live runs to trip the test account's real 6-attempt lockout -- it
  actually happened. `_handle_email_step_if_present`/`_handle_password_step_if_present`
  now always submit the correct value directly, no `run_negative_check` parameter at
  all. That negative check still exists, but only in the separate, deliberately-invoked
  `tools/adhoc/test_negative_path_error_messages.py` script -- run it by hand only when
  specifically re-verifying error-message wording, never as part of routine testing.
- **OTP is the one exception that still gets a wrong-value attempt in the default flow,
  confirmed by the user (2026-10-06): its wrong-value attempt is followed by clicking
  the OTP page's own Cancel button (below Verify), never the correct code in that same
  pass.** This stays in `SignInFlow.run()`'s own default behavior (`_handle_otp_step`'s
  `run_negative_check` parameter, `_run_fresh_auth_with_retry`'s attempt-0 gating) because
  it isn't purely a negative-path check -- it's also how the cancel-and-retry mechanism
  itself gets exercised every run. Every run's first whole-flow attempt deliberately
  fails by design; the retry pass that follows submits correct email/password/OTP
  directly (no repeated negative checks anywhere on that pass).
- **The post-OTP transition screen ("...getting things ready" / "Starting the migration
  assistant") is not a reliable success signal by itself.** It can appear even when
  sign-in was cancelled or failed. Always race it against the "There was a problem
  signing in" / "Sign-in failed. Please try again." dialog; on failure, click that
  dialog's own Retry button and repeat the whole Email→Password→OTP sequence, never
  just the OTP step. **There is no separate "cancel path" distinct from "retry on
  failure"** -- the OTP negative check's deliberate Cancel and a genuine failure both
  resolve through this exact same race and the exact same Retry button.
- **Cancelling still triggers a real Windows UAC prompt -- it's not a UAC-free
  shortcut.** After clicking Cancel, a human still has to approve UAC before the
  "There was a problem signing in" dialog appears. Give that wait the full remaining
  time budget, not a short fixed window, same reasoning as the success path's own UAC
  wait.
- **The only Cancel buttons still excluded from `SignInFlow.run()`'s normal production
  path** are the "Sign in to MyDell to continue" wait modal, the sign-in-failed
  dialog's own Cancel, and the confirm-accounts dialog's Cancel -- those remain genuine
  destructive user choices, never automated.
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
- **Never enumerate browser windows via `Get-Process ... .MainWindowHandle`.** Confirmed
  live (2026-10-05): that property reports only ONE window per process object, and the
  OS routinely opens the sign-in window inside an ALREADY-RUNNING browser process
  (reusing it) instead of spawning a new one -- the new window was then structurally
  invisible to detection, not just slow to appear, and no amount of extra patience or
  retries would have found it. `factory/browser_driver_factory.py`'s
  `list_browser_window_hwnds()` now uses real Win32 `EnumWindows` (via a cached .ps1
  file invoked with `-File`, not inline `-Command` text -- the C# source's own double
  quotes break a double-quoted PowerShell here-string). Build on that function; don't
  reintroduce the `MainWindowHandle` approach.
- **A genuinely new top-level window is NOT guaranteed, even past the EnumWindows fix.**
  Confirmed live (2026-10-06): the OS sometimes opens the Dell sign-in page as a new TAB
  inside an ALREADY-RUNNING browser window instead of a new window -- the email field
  was visibly showing (browser autofill even prefilled it), but automation never typed
  into it, because no hwnd was ever "new" relative to the pre-click snapshot, so the
  snapshot-diff check waited out its full timeout and `_click_sign_in_with_retry`
  wrongly concluded no browser had opened. Fixed in
  `find_new_browser_window_hwnd()`: it now falls back to matching by window/tab title
  (confirmed "Sign In | Dell US", see `SIGN_IN_WINDOW_TITLE_KEYWORDS` in
  `factory/config.py`) across ALL currently open browser windows, not just new ones,
  whenever the new-hwnd check finds nothing. This fixes all three call sites at once
  (`_click_sign_in_with_retry`, `_wait_for_new_browser`,
  `attach_to_new_sign_in_browser`) since they all go through this one function.
- **Disable browser autofill proactively, same pattern as the Restore-pages fix.**
  `factory/prerequisites.py`'s `_disable_autofill_suggestions()` patches the Chrome/Edge
  profile's `Preferences` JSON (`autofill.profile_enabled` / `autofill.credit_card_enabled`
  set to `false`) before each run, so a saved email/address never gets silently
  prefilled into a field in place of the username automation actually types.
- **Nothing in `tools/` may hardcode a build path or credentials.** Confirmed directly
  by the user (2026-10-06): this must run consistently on any machine, not just the one
  it was written on. `tools/run_sign_in_flow.py` is the reference pattern (env-var
  credentials via `_require_env()`, build path via `--build-path`/prompt);
  `tools/_test_full_signin.py` and `tools/_test_cancel_and_retry_live.py` follow the
  same env-var convention (`DDA_TARGET_BUILD_PATH`, `DDA_TARGET_SIGNIN_USERNAME`,
  `DDA_TARGET_SIGNIN_PASSWORD`, `DDA_TARGET_OTP_STATIC_VALUE` -- see `.env.example`).
  Any new throwaway test script must do the same, not hardcode `r"C:\Users\...\"`.
- **`tools/adhoc/` is for deliberately-invoked, non-routine checks only** -- currently
  just `test_negative_path_error_messages.py`. Anything placed there must NOT be run as
  part of normal/routine testing (that's the whole point: it exists so a lockout-risking
  check has a home outside the default flow). Follow the same env-var and
  `except BaseException` cleanup conventions as every other script here.
