"""Assertion helpers for page objects."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from playwright.sync_api import Frame, Locator, Page

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

        assert not self._has_visible_login_form(), (
            f"Page contains a visible login form, current URL: {self.page.url}"
        )

        error_indicators = [
            # ---- 技术级错误页 ----
            "404 Not Found",
            "404页面不存在",
            "500 Internal Server Error",
            "500错误",
            "页面不存在",
            "系统异常",
            "应用异常",
            "加载失败",
            "Whitelabel Error Page",
            # ---- 业务级错误提示（2026-11-17 走查补充）----
            # 起因：门户「开发者平台→开发者社区」跳 zone.cscec.com 后提示
            # 「租户错误」，页面本身正常渲染，旧词表识别不到，用例全绿通过。
            # 只收「强组合词」：像「未开通」「请选择租户」这类同时是正常状态
            # 标签的词**不能**放进来，否则租户列表页会大面积误报。
            "租户错误",
            "租户不存在",
            "租户未开通",
            "无权访问该页面",
            "没有访问权限",
            "无权限访问",
            "系统繁忙",
            "服务暂不可用",
            "服务不可用",
            "数据加载异常",
        ]
        first_screen_text = compact_text[:3000]
        for indicator in error_indicators:
            assert indicator not in first_screen_text, (
                f"Page contains error indicator '{indicator}', current URL: {self.page.url}"
            )
        return self

    # 业务级错误提示（跨域落地页同样适用）。只收强组合词，
    # 避免「未开通」「请选择租户」这类正常状态标签造成误报。
    BIZ_ERROR_INDICATORS = (
        "租户错误",
        "租户不存在",
        "租户未开通",
        "无权访问该页面",
        "没有访问权限",
        "无权限访问",
        "系统繁忙",
        "服务暂不可用",
        "服务不可用",
        "数据加载异常",
        "该应用不存在",
        "应用已下线",
    )

    def landing_page_healthy(
        self,
        expected_host: str | None = None,
        expected_texts: tuple[str, ...] = (),
    ) -> "AssertionHelper":
        """校验「点了一个入口跳过去」之后的落地页是否真的可用。

        起因（2026-11-17 生产走查）：门户「开发者平台 → 开发者社区」跳转到
        zone.cscec.com 后提示「租户错误」。目标页本身正常渲染，
        `page_not_blank_or_error()` 只识别 404/500 类技术错误页，因此全绿通过；
        而该用例当时也没有任何内容断言，等于只验了「点得动」。

        三层判据：域名正确 → 无业务错误提示 → 出现期望内容。
        """
        # 1) 域名
        if expected_host:
            current = urlparse(self.page.url).netloc.lower()
            assert expected_host.lower() in current, (
                f"跳转后域名不符：期望包含 {expected_host}，实际 {self.page.url}"
            )

        # 2) 业务错误提示
        body = self.page.locator("body")
        body.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        text = " ".join(body.inner_text(timeout=settings.ACTION_TIMEOUT).split())
        assert text, f"落地页正文为空，当前 URL: {self.page.url}"
        for indicator in self.BIZ_ERROR_INDICATORS:
            assert indicator not in text, (
                f"落地页出现业务错误提示「{indicator}」，当前 URL: {self.page.url}"
            )

        # 3) 期望内容
        if expected_texts:
            hit = [t for t in expected_texts if t in text]
            assert hit, (
                f"落地页未包含任何期望内容 {list(expected_texts)}，"
                f"当前 URL: {self.page.url}，正文前 200 字: {text[:200]}"
            )

        # 技术级错误页仍复用既有判据
        self.page_not_blank_or_error()
        return self

    def _has_visible_login_form(self) -> bool:
        """Detect login controls, not credential words in business details."""
        login_name = re.compile(r"^(?:登\s*录|log\s*in|sign\s*in)$", re.I)
        for frame in self.page.frames:
            if not self._frame_is_visible(frame):
                continue
            for password in frame.locator('input[type="password"]').all():
                if not password.is_visible() or not password.is_editable():
                    continue
                # Keep a site's navigation login link outside a business form.
                forms = frame.locator("form").filter(has=password)
                scope = forms.first if forms.count() else frame.locator("body")
                login_controls = scope.get_by_role("button", name=login_name).or_(
                    scope.get_by_role("link", name=login_name)
                ).or_(scope.locator("#pwdLoginButton"))
                if any(control.is_visible() for control in login_controls.all()):
                    return True
        return False

    @staticmethod
    def _frame_is_visible(frame: Frame) -> bool:
        """Exclude login widgets hidden by any ancestor iframe."""
        current = frame
        while current.parent_frame is not None:
            if not current.frame_element().is_visible():
                return False
            current = current.parent_frame
        return True
