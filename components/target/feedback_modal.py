"""Target-role "Tell us how we did" feedback modal (FeedbackModal), opened from the
Migration Done screen's tile of the same name -- actions only: pick a star rating, type
a comment, Submit or Cancel. Submit stays disabled until BOTH a rating and a non-blank
comment are given (FeedbackModal.tsx's canSubmit). See
assertions/target/feedback_modal.py's is_showing().

Verified against source, not live: rebit TargetPc.UI
web/src/screens/results/FeedbackModal.tsx + components/common/StarRating.tsx; resx keys
Buttons_Submit, Buttons_Cancel, MigrationDone_FeedbackRatingAria. The comment
textarea's UIA mapping (AutomationId="feedback-comment") is unverified -- see
locators/target/feedback_modal.py.
"""

from components.base_component import BaseComponent
from locators.target.feedback_modal import (
    CANCEL_BUTTON_LOCATOR,
    COMMENT_TEXTAREA_LOCATOR,
    STAR_RATING_MAX,
    SUBMIT_BUTTON_LOCATOR,
    star_rating_button_locator,
)


class FeedbackModal:
    def __init__(self, app_session):
        self._session = app_session
        self._submit_button = BaseComponent(app_session, *SUBMIT_BUTTON_LOCATOR, "FeedbackSubmitButton")
        self._cancel_button = BaseComponent(app_session, *CANCEL_BUTTON_LOCATOR, "FeedbackCancelButton")
        self._comment_textarea = BaseComponent(app_session, *COMMENT_TEXTAREA_LOCATOR, "FeedbackCommentTextarea")

    def click_submit(self) -> None:
        self._submit_button.click()

    def click_cancel(self) -> None:
        self._cancel_button.click()

    def set_rating(self, stars) -> None:
        """Clicks the star button for `stars` (1..5, or a half step such as 2.5 -- the
        control exposes a separate invisible button per half star). The buttons are
        zero-size hit targets layered over the star icon, so this uses click_at_center()
        rather than a UIA Invoke, same as the other WebView2 buttons in this app that
        were confirmed live to ignore Invoke."""
        value = float(stars)
        if value <= 0 or value > STAR_RATING_MAX or (value * 2) != int(value * 2):
            raise ValueError(f"stars must be a half-step value between 0.5 and {STAR_RATING_MAX}, got {stars}")
        star_button = BaseComponent(self._session, *star_rating_button_locator(value), f"StarRating{value}")
        star_button.click_at_center()

    def type_comment(self, text: str) -> None:
        self._comment_textarea.click()
        self._comment_textarea.type_text(text)
