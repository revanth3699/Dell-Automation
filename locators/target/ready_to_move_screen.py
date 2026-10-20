"""Locators for components.target.ready_to_move_screen.ReadyToMoveScreen -- click-target
locator only. The heading assertion locator lives in
assertions/target/ready_to_move_screen.py instead.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/migration-setup/ReadyToMoveStage.tsx passes onCancel to StageCard with
no cancelLabel, so web/src/components/stage/StageCard.tsx renders a plain <button>
labelled t('Buttons_Cancel') = "Cancel" (Resources/Resources.resx) plus an aria-hidden
"x" icon -- accessible Name "Cancel", a Button control.
"""

CANCEL_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Cancel"]')
