"""
文档中心页面

文档中心是中建云门户下的子模块，通过独立 URL 直接访问。
提供文档中心相关的操作封装。
"""

from urllib.parse import urlparse

from playwright.sync_api import Page

from core.base_page import BasePage
from core.logger import get_logger
from config.settings import settings

logger = get_logger("doc_center_page")


class DocCenterPage(BasePage):
    """文档中心页面"""

    PAGE_NAME = "文档中心"
    PAGE_URL_PATTERN = "workbench|doc|document|knowledge"

    def __init__(self, page: Page):
        super().__init__(page)

    # ── 导航 ──

    def open(self) -> "DocCenterPage":
        """打开文档中心"""
        self.nav.goto_url(settings.DOC_CENTER_URL)
        logger.info("[导航] → 文档中心")
        return self

    # ── 功能操作 ──

    def navigate_to_workspace(self) -> "DocCenterPage":
        """导航到工作台"""
        self.elements.click_candidates(
            [
                ("text", "工作台"),
                ("css", "a[href*='workbench']"),
            ],
            description="工作台",
        )
        self.nav.wait_ready()
        return self

    def navigate_to_my_documents(self) -> "DocCenterPage":
        """导航到我的文档"""
        self.elements.click_candidates(
            [
                ("text", "我的文档"),
                ("css", "a[href*='mydoc']"),
            ],
            description="我的文档",
        )
        self.nav.wait_ready()
        return self

    def search_document(self, keyword: str) -> "DocCenterPage":
        """搜索文档"""
        search_input = self.elements.find_candidates(
            [
                ("placeholder", "搜索"),
                ("css", "input[placeholder*='搜索']"),
                ("css", ".ant-input-search input"),
            ],
            description="搜索框",
        )
        if search_input:
            search_input.fill(keyword)
            self.elements.click_candidates(
                [
                    ("css", ".ant-input-search-button"),
                    ("css", "button[type='submit']"),
                ],
                description="搜索按钮",
            )
            self.nav.wait_ready()
        return self

    # ── Assertions ──

    def should_be_on_doc_center(self) -> "DocCenterPage":
        """断言在文档中心页面"""
        current_url = self.page.url.lower()
        expected_host = urlparse(settings.DOC_CENTER_URL).netloc.lower()
        assert expected_host in current_url and any(
            kw in current_url for kw in ["workbench", "doc", "document", "knowledge"]
        ), \
            f"期望在文档中心页面，当前 URL: {self.page.url}"
        self.assertions.any_text_visible(["文档中心", "工作台", "我的文档"])
        logger.info("[断言] 当前在文档中心")
        return self

    def should_see_workspace(self) -> "DocCenterPage":
        """断言工作台可见"""
        self.assertions.text_visible("工作台")
        return self
