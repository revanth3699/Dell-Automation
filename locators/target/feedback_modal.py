"""Locators for components.target.feedback_modal.FeedbackModal -- click/type-target
locators only. The body-text assertion locator lives in
assertions/target/feedback_modal.py instead.

Verified against source, not live: rebit TargetPc.UI
web/src/screens/results/FeedbackModal.tsx (Resources/Resources.resx):
- SUBMIT/CANCEL: a PopUpModelFooter of two DDSButtons, secondary t('Buttons_Cancel') =
  "Cancel" and primary t('Buttons_Submit') = "Submit" (disabled until both a star and a
  non-blank comment are given).
- STAR_RATING_ARIA_TEMPLATE: components/common/StarRating.tsx renders, per star, TWO
  invisible <button>s (left half / right half) with
  aria-label=t('MigrationDone_FeedbackRatingAria', {value, max}) =
  "Rate {{value}} out of {{max}} stars", max defaulting to 5 -- so the Names are
  "Rate 0.5 out of 5 stars", "Rate 1 out of 5 stars", ... "Rate 5 out of 5 stars".
  star_rating_button_locator() builds the exact-Name Button locator for one value.
- COMMENT_TEXTAREA_LOCATOR: a DDSTextArea with id="feedback-comment" (DDSTextArea's props
  extend TextareaHTMLAttributes, so the id is expected to reach the <textarea>). The
  UIA mapping is UNVERIFIED: Chromium/WebView2 is expected to expose the HTML id as the
  element's AutomationId and a <textarea> as an Edit control, but neither has been
  confirmed against this app's live element tree. If this never matches, try //Edit
  (the modal has exactly one text field) and confirm via a raw //Edit dump.
"""

SUBMIT_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Submit"]')
CANCEL_BUTTON_LOCATOR = ("xpath", '//Button[@Name="Cancel"]')
COMMENT_TEXTAREA_LOCATOR = ("xpath", '//*[@AutomationId="feedback-comment"]')

STAR_RATING_MAX = 5
STAR_RATING_ARIA_TEMPLATE = "Rate {value} out of {max} stars"


def star_rating_button_locator(value) -> tuple:
    """Locator for the invisible half/whole-star button whose aria-label names `value`
    (0.5 .. STAR_RATING_MAX in 0.5 steps). Whole numbers are formatted without a
    decimal point, matching how react-i18next interpolates the JS number (3 -> "3",
    2.5 -> "2.5")."""
    value_text = str(int(value)) if float(value).is_integer() else str(value)
    name = STAR_RATING_ARIA_TEMPLATE.format(value=value_text, max=STAR_RATING_MAX)
    return ("xpath", f'//Button[@Name="{name}"]')
