"""Expected heading text + locator + assertion function for
components.target.skipped_files_screen.SkippedFilesScreen -- the skipped-files detail
screen reached from the results summary when the report has failures.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/results/SkippedFilesView.tsx renders a StagePanel titled
t('SkippedFiles_Title') = "We couldn’t transfer all of your files"
(Resources/Resources.resx). Curly apostrophe in "couldn’t", so this matches the
apostrophe-free substring via contains(). Never a click target, so it lives here.
"""

from assertions.common import text_exists

HEADING_CONTAINS_TEXT = "transfer all of your files"
SKIPPED_FILES_HEADING_LOCATOR = ("xpath", f'//*[contains(@Name, "{HEADING_CONTAINS_TEXT}")]')


def is_showing(session, timeout: float = 2.0) -> bool:
    return text_exists(session, SKIPPED_FILES_HEADING_LOCATOR, "SkippedFilesHeading", timeout=timeout)
