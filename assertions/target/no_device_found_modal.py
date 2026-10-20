"""Expected heading text + locator + assertion function for
components.target.no_device_found_modal.NoDeviceFoundModal -- the engine's
discovery-timeout notice (Pairing.Confirmation FailureCode 2500), shown over the
Connect Old PC / Enter Code screens.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/migration-setup/NoDeviceFoundModal.tsx renders a PopUpModel whose title
is t('ConnectOldPc_NoDeviceFoundModalTitle') = "Connect your other PC to {0}"
(Resources/Resources.resx) with {0} replaced at runtime by the live network name (or
the ConnectOldPc_Step2Fallback copy), so only the fixed prefix is matched, via
contains(). Never a click target, so it lives here.
"""

from assertions.common import text_exists

HEADING_CONTAINS_TEXT = "Connect your other PC to"
NO_DEVICE_FOUND_HEADING_LOCATOR = ("xpath", f'//*[contains(@Name, "{HEADING_CONTAINS_TEXT}")]')


def is_showing(session, timeout: float = 0.1) -> bool:
    return text_exists(session, NO_DEVICE_FOUND_HEADING_LOCATOR, "NoDeviceFoundHeading", timeout=timeout)
