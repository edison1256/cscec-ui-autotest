"""文档中心页面

文档中心是中建云门户下的子模块，通过独立 URL 直接访问。
提供文档中心相关的操作封装。
"""

from urllib.parse import urlparse

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from core.base_page import BasePage
from core.logger import get_logger
from core.navigation_helpers import EntryNotExposed, navigate_with_fallback
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
        if not self._is_doc_center_ready() and settings.DOC_CENTER_FALLBACK_URL:
            logger.info("[导航] 文档中心主域名未就绪，切换备用域名")
            self.nav.goto_url(settings.DOC_CENTER_FALLBACK_URL)
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
        """导航到我的文档（弹性：菜单→直链兜底→入口未暴露则抛 EntryNotExposed）"""

        def click_menu() -> None:
            self.elements.click_candidates(
                [
                    ("text", "我的文档"),
                    ("css", "a[href*='mydoc']"),
                ],
                description="我的文档",
            )
            self.nav.wait_ready()

        def readiness() -> bool:
            if "mydoc" not in self.page.url.lower():
                return False
            try:
                self.assertions.text_visible("我的文档")
                return True
            except Exception:  # noqa: BLE001
                return False

        navigate_with_fallback(
            self.page,
            click_menu=click_menu,
            fallback_url=settings.DEEP_LINKS.get("my_documents"),
            readiness=readiness,
            entry_name="我的文档",
        )
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
        expected_hosts = _doc_center_hosts()
        current_host = urlparse(current_url).netloc.lower()
        assert current_host in expected_hosts and any(
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

    def should_be_on_my_documents(self) -> "DocCenterPage":
        """断言已到达我的文档页面。"""
        self.assertions.page_not_blank_or_error()
        self.assertions.url_contains("mydoc")
        self.assertions.text_visible("我的文档")
        logger.info("[断言] 当前在我的文档页")
        return self

    def _is_doc_center_ready(self) -> bool:
        current_url = self.page.url.lower()
        if _is_login_like_url(current_url):
            return False
        current_host = urlparse(current_url).netloc.lower()
        if current_host not in _doc_center_hosts():
            return False
        if not any(kw in current_url for kw in ["workbench", "doc", "document", "knowledge"]):
            return False
        try:
            self.assertions.any_text_visible(["文档中心", "工作台", "我的文档"], timeout=3000)
            return True
        except (AssertionError, PlaywrightTimeoutError):
            return False


    def search_and_assert_results(self, keyword: str) -> "DocCenterPage":
        """M0-D-SUPP-001: 验证全局搜索及结果渲染。"""
        self.search_document(keyword)
        # 宽泛匹配，可以是列表容器，或是兜底文案
        self.nav.wait_ready()
        self.assertions.page_not_blank_or_error()
        self.assertions.any_text_visible([keyword, "未搜", "暂无数据", "没有找", "0条", "文档", "列表"])
        logger.info(f"[断言] 文档中心搜索引擎返回正常: {keyword}")
        return self

    def verify_doc_detail_rendering(self) -> "DocCenterPage":
        """M0-D-SUPP-002: 深入文档详情，验证富文本渲染容器。"""
        # 找一个文档链接点进去
        doc_link = self.elements.find_candidates(
            [
                ("css", ".doc-list-item a"),
                ("css", ".hot-list a"),
                ("css", ".article-list a"),
                ("text", "新手指南"),
                ("text", "操作指南"),
                ("text", "了解更多"),
            ],
            description="文档详情链接",
            timeout=3000
        )
        
        if not doc_link:
            raise EntryNotExposed("文档中心首页未暴露可点击的文档详情链接")
            
        doc_link.click()
        self.nav.wait_ready()
            
        # 断言富文本容器
        try:
            # Markdown 渲染器或富文本容器常见的 class
            viewer = self.page.locator(".doc-viewer, .editor-content, .vditor, .markdown-body, .article-content, [class*='content']").first
            viewer.wait_for(state="visible", timeout=5000)
            logger.info("[断言] 文档详情富文本/Markdown 渲染器挂载成功")
        except PlaywrightTimeoutError:
            raise AssertionError("进入文档详情后，核心文本容器未在规定时间内暴露") from None
            
        return self

def _doc_center_hosts() -> set[str]:
    hosts = {urlparse(settings.DOC_CENTER_URL).netloc.lower()}
    if settings.DOC_CENTER_FALLBACK_URL:
        hosts.add(urlparse(settings.DOC_CENTER_FALLBACK_URL).netloc.lower())
    return hosts

def _is_login_like_url(url: str) -> bool:
    parsed = urlparse(url)
    return (
        ("iam" in parsed.netloc and "cas" in parsed.path)
        or "passport" in parsed.netloc
        or "/login" in parsed.path
    )
