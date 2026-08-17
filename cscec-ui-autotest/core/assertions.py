"""Assertion helpers for page objects."""

from __future__ import annotations

from urllib.parse import urlparse

from playwright.sync_api import Locator, Page

from config.settings import settings
from core.logger import get_logger


logger = get_logger("assertions")


class AssertionHelper:
    """Page-level assertions with consistent timeouts and messages."""

    def __init__(self, page: Page):
        self.page = page

    def text_visible(self, text: str, timeout: int | None = None) -> "AssertionHelper":
        self.page.wait_for_selector(f"text={text}", timeout=timeout or settings.ACTION_TIMEOUT)
        return self

    def texts_visible(self, texts: list[str], timeout: int | None = None) -> "AssertionHelper":
        for text in texts:
            self.text_visible(text, timeout=timeout)
        return self

    def any_text_visible(self, texts: list[str], timeout: int | None = None) -> "AssertionHelper":
        # 1. 先快速检查已有可见项
        for text in texts:
            if self.page.locator(f"text={text}").first.is_visible():
                logger.debug(f"[Assert] text visible: {text}")
                return self

        # 2. 结合联合 locator 等待任意一个可见
        combined_selector = ", ".join([f"text={t}" for t in texts])
        try:
            self.page.locator(combined_selector).first.wait_for(state="visible", timeout=timeout or settings.ACTION_TIMEOUT)
            return self
        except Exception as exc:
            raise AssertionError(f"None of these texts are visible: {texts}. Last error: {exc}")

    def text_hidden(self, text: str) -> "AssertionHelper":
        assert not self.page.locator(f"text={text}").first.is_visible(), f"Text should be hidden: {text}"
        return self

    def element_visible(self, locator: Locator, description: str = "") -> "AssertionHelper":
        desc = description or "target element"
        assert locator.is_visible(), f"{desc} is not visible"
        return self

    def url_contains(self, text: str) -> "AssertionHelper":
        assert text.lower() in self.page.url.lower(), f"Expected URL to contain {text}, current URL: {self.page.url}"
        return self

    def url_matches_any(self, patterns: list[str], page_name: str = "page") -> "AssertionHelper":
        current_url = self.page.url.lower()
        assert any(pattern in current_url for pattern in patterns), (
            f"Expected to be on {page_name}, current URL: {self.page.url}"
        )
        return self

    def page_not_blank_or_error(self) -> "AssertionHelper":
        body = self.page.locator("body")
        body.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        body_text = body.inner_text(timeout=settings.ACTION_TIMEOUT)
        compact_text = " ".join(body_text.split())
        assert compact_text, f"Page body is blank, current URL: {self.page.url}"

        parsed = urlparse(self.page.url.lower())
        login_like_url = (
            ("iam" in parsed.netloc and "cas" in parsed.path)
            or "passport" in parsed.netloc
            or "/login" in parsed.path
        )
        assert not login_like_url, f"Page redirected to login-like URL: {self.page.url}"

        login_form_like = "密码" in compact_text and ("用户名" in compact_text or "账号" in compact_text)
        assert not login_form_like, f"Page looks like a login form, current URL: {self.page.url}"

        error_indicators = [
            "404 Not Found",
            "404页面不存在",
            "500 Internal Server Error",
            "500错误",
            "页面不存在",
            "系统异常",
            "应用异常",
            "加载失败",
            "Whitelabel Error Page",
        ]
        first_screen_text = compact_text[:3000]
        for indicator in error_indicators:
            assert indicator not in first_screen_text, (
                f"Page contains error indicator '{indicator}', current URL: {self.page.url}"
            )
        return self
