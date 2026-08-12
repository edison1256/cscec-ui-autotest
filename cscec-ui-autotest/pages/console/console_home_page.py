"""
控制台首页 — 登录后进入的主工作区

提供控制台内的功能导航入口。
"""

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from config.settings import settings
from core.base_page import BasePage
from core.logger import get_logger

logger = get_logger("console_home_page")


class ConsoleHomePage(BasePage):
    """控制台首页"""

    PAGE_NAME = "控制台首页"
    PAGE_URL_PATTERN = "console"

    def __init__(self, page: Page):
        super().__init__(page)

    # ── 导航 ──

    def navigate_to_service_supply(self) -> "ConsoleHomePage":
        """导航到服务供给"""
        self.elements.click_candidates(
            [
                ("text", "服务供给"),
                ("css", "a[href*='service']"),
            ],
            description="服务供给",
        )
        self.nav.wait_ready()
        return self

    def navigate_to_project_mgmt(self) -> "ConsoleHomePage":
        """导航到项目管理"""
        self.elements.click_candidates(
            [
                ("text", "项目管理"),
                ("css", "a[href*='project']"),
            ],
            description="项目管理",
        )
        self.nav.wait_ready()
        return self

    def navigate_to_process_mgmt(self) -> "ConsoleHomePage":
        """导航到流程管理"""
        self.elements.click_candidates(
            [
                ("text", "流程管理"),
                ("css", "a[href*='process']"),
            ],
            description="流程管理",
        )
        self.nav.wait_ready()
        return self

    # ── Assertions ──

    def should_be_on_console(self) -> "ConsoleHomePage":
        """断言在控制台页面"""
        self.assertions.page_not_blank_or_error()
        self.assertions.any_text_visible(["控制台", "服务中心", "常用模块", "应用资源"])
        logger.info("[断言] 当前在控制台")
        return self

    def should_be_readonly_page_ready(self, expected_texts: list[str]) -> "ConsoleHomePage":
        """断言控制台只读页面可正常展示。"""
        self.assertions.page_not_blank_or_error()
        self.assertions.texts_visible(expected_texts)
        logger.info("[断言] 控制台只读页面正常展示")
        return self

    def fill_and_clear_menu_search(self, value: str = "readonly-check") -> "ConsoleHomePage":
        """对控制台菜单搜索框执行填充和清空。"""
        search_input = self.page.get_by_placeholder("请输入菜单名称").first
        search_input.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        search_input.fill(value)
        assert search_input.input_value() == value, "控制台菜单搜索框未成功填充"
        search_input.clear()
        assert search_input.input_value() == "", "控制台菜单搜索框未成功清空"
        logger.info("[只读交互] 控制台菜单搜索框填充清空")
        return self

    def open_all_menu_view(self) -> "ConsoleHomePage":
        """尽量打开控制台全部菜单视图，并确认当前菜单区可见。"""
        trigger = self.page.get_by_text("查看全部菜单", exact=True).first
        try:
            trigger.wait_for(state="visible", timeout=2000)
            trigger.click()
            self.nav.wait_ready()
        except PlaywrightTimeoutError:
            logger.info("[只读交互] 未发现“查看全部菜单”，继续使用当前菜单视图")

        self.assertions.any_text_visible(["常用模块", "资源管理", "订阅服务", "工作台"])
        logger.info("[断言] 控制台菜单视图可见")
        return self

    def should_show_menu_group(self, group_name: str, item_names: list[str]) -> "ConsoleHomePage":
        """断言控制台菜单组可见，记录已展开的核心菜单项。"""
        self.assertions.text_visible(group_name)
        visible_items = []
        for item_name in item_names:
            try:
                self.assertions.text_visible(item_name, timeout=1000)
                visible_items.append(item_name)
            except Exception:
                continue
        if visible_items:
            logger.info(f"[断言] 菜单组子项可见: {group_name} -> {visible_items}")
        else:
            logger.info(f"[断言] 菜单组子项未默认展开: {group_name}")
        logger.info(f"[断言] 菜单组可见: {group_name}")
        return self

    def navigate_to_flow_page(self) -> "ConsoleHomePage":
        """从全部菜单进入流程页面。"""
        self.open_all_menu_view()
        flow_entry = self.page.get_by_text("流程", exact=True).last
        flow_entry.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        flow_entry.click()
        self.nav.wait_ready()
        self.assertions.url_contains("flowmodel")
        logger.info("[导航] → 流程")
        return self
