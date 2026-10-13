"""Locators for components.source.transfer_progress_screen -- click-target locators
only. Every heading/body assertion locator for this screen family lives in
assertions/source/transfer_progress_screen.py instead (never click targets).

Confirmed via user-supplied screenshots (2026-10-13): this screen family's final
outcomes do NOT all share one click target --

  - "We've completed your migration." (full success) has an explicit "Close" button.
  - "Your migration summary is ready." (one of two partial-migration outcomes) ALSO
    has a "Close" button, same accessible name -- CLOSE_BUTTON_LOCATOR covers both.
  - "Your migration is now complete." (the OTHER partial-migration outcome) has only a
    "Try Again" button plus the screen's own top-right close icon (X) -- there is no
    "Close"-named button on this screen, so CLOSE_BUTTON_LOCATOR (scoped to Button, per
    the WindowsCaptionButton-collision gotcha already hit elsewhere in this project --
    see locators/target/restore_pages_dialog.py) does not match it. Dismissed via
    CLOSE_ICON_LOCATOR instead.
  - "We ran into a problem during your migration." (a recoverable error, not a final
    outcome) has its own "Try Again" button that restarts the migration --
    TRY_AGAIN_BUTTON_LOCATOR. Same accessible name as "Your migration is now
    complete."'s own "Try Again" button, but that one is never clicked (its screen is
    dismissed via the close icon instead) -- TRY_AGAIN_BUTTON_LOCATOR is only ever
    clicked from the error-screen path.

Bug fixed here, confirmed by the user via two separate live runs (2026-10-13): this
file originally assumed all final screens shared one "Close" button (wrong for "Your
migration is now complete."), then after that fix assumed "Your migration is now
complete." was the ONLY partial-migration outcome and dropped "Your migration summary
is ready." entirely -- which turned out to be a second, equally real partial outcome
with its own "Close" button. See assertions/source/transfer_progress_screen.py's
module docstring for the full history.
"""

CLOSE_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Close"]')
CLOSE_ICON_LOCATOR = ("xpath", '//ImageButton[@Name="Close"]')
TRY_AGAIN_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Try Again"]')
