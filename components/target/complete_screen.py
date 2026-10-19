"""Target-role "Your transfer is complete" detail screen (CompleteView) -- actions only:
the header "Back to summary" link and the "Open a PDF report" link. See
assertions/target/complete_screen.py's is_showing() (which AND-gates the heading with
the Back to summary link, since the heading alone is shared with the results summary).

Verified against source, not live: rebit TargetPc.UI
web/src/screens/results/CompleteView.tsx; resx keys Complete_BackToSummary,
Complete_OpenPdfCtaTitle. Note "Open a PDF report" is inert (aria-disabled, click
handler no-ops) until the report file exists -- a successful click() here does not
guarantee the PDF opened.
"""

from components.base_component import BaseComponent
from locators.target.complete_screen import BACK_TO_SUMMARY_LINK_LOCATOR, OPEN_PDF_LINK_LOCATOR


class CompleteScreen:
    def __init__(self, app_session):
        self._back_to_summary_link = BaseComponent(app_session, *BACK_TO_SUMMARY_LINK_LOCATOR, "BackToSummaryLink")
        self._open_pdf_link = BaseComponent(app_session, *OPEN_PDF_LINK_LOCATOR, "OpenPdfReportLink")

    def click_back_to_summary(self) -> None:
        self._back_to_summary_link.click()

    def click_open_pdf(self) -> None:
        self._open_pdf_link.click()
