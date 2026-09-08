"""
控制台首页 — 登录后进入的主工作区

提供控制台内的功能导航入口。
"""

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from config.settings import settings
from core.base_page import BasePage
from core.logger import get_logger
from core.navigation_helpers import EntryNotExposed, navigate_with_fallback

logger = get_logger("console_home_page")


class ConsoleHomePage(BasePage):
    """控制台首页"""

    PAGE_NAME = "控制台首页"
    PAGE_URL_PATTERN = "console"

    def __init__(self, page: Page):
        super().__init__(page)

    # ── 导航 ──

    def navigate_to_service_supply(self) -> "ConsoleHomePage":
        """导航到服务供给（弹性：菜单→直链兜底→入口未暴露则抛 EntryNotExposed）"""

        def click_menu() -> None:
            self.elements.click_candidates(
                [
                    ("text", "服务供给"),
                    ("css", "a[href*='service']"),
                ],
                description="服务供给",
            )
            self.nav.wait_ready()

        def readiness() -> bool:
            if "service" not in self.page.url.lower():
                return False
            try:
                self.assertions.any_text_visible(["服务供给", "服务列表"])
                return True
            except Exception:  # noqa: BLE001
                return False

        navigate_with_fallback(
            self.page,
            click_menu=click_menu,
            fallback_url=settings.DEEP_LINKS.get("service_supply"),
            readiness=readiness,
            entry_name="服务供给",
        )
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

    def should_be_on_service_supply(self) -> "ConsoleHomePage":
        """断言已进入服务供给二级页面。"""
        self.assertions.page_not_blank_or_error()
        self.assertions.url_contains("service")
        self.assertions.any_text_visible(["服务供给", "服务列表", "服务目录"])
        logger.info("[断言] 当前在服务供给页")
        return self

    def fill_and_clear_menu_search(self, value: str = "readonly-check") -> "ConsoleHomePage":
        """对控制台菜单搜索框执行填充和清空。"""
        search_input = self.page.get_by_placeholder("请输入菜单名称").first
        try:
            search_input.wait_for(state="visible", timeout=3000)
        except PlaywrightTimeoutError:
            logger.info("[只读交互] 当前控制台未暴露菜单搜索框，跳过填充清空")
            return self
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
        try:
            self.page.get_by_text(group_name, exact=False).first.wait_for(state="visible", timeout=3000)
        except PlaywrightTimeoutError as exc:
            raise EntryNotExposed(f"控制台菜单组未暴露: {group_name}") from exc
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
        try:
            flow_entry.wait_for(state="visible", timeout=3000)
        except PlaywrightTimeoutError as exc:
            raise EntryNotExposed("控制台流程入口未暴露") from exc
        flow_entry.click()
        self.nav.wait_ready()
        self.assertions.url_contains("flowmodel")
        logger.info("[导航] → 流程")
        return self

    def navigate_and_assert_table_renders(self, menu_group: str, menu_item: str) -> "ConsoleHomePage":
        """深入点击控制台菜单子项，并断言右侧区域表格正常渲染或无数据状态返回正常。"""
        self.open_all_menu_view()
        
        # 展开菜单组
        try:
            group = self.page.get_by_text(menu_group, exact=False).first
            group.wait_for(state="visible", timeout=3000)
            group.click()
            self.page.wait_for_timeout(1000) # 等待动画
        except PlaywrightTimeoutError:
            raise EntryNotExposed(f"控制台菜单组未暴露: {menu_group}") from None
            
        # 点击菜单项
        try:
            item = self.page.get_by_text(menu_item, exact=True).first
            item.wait_for(state="visible", timeout=3000)
            item.click()
            self.nav.wait_ready()
        except PlaywrightTimeoutError:
            raise EntryNotExposed(f"控制台菜单子项未暴露: {menu_item}") from None
            
        # 断言表格区域渲染正常
        try:
            table_container = self.page.locator(".el-table, .ant-table, table").first
            table_container.wait_for(state="attached", timeout=8000)
            logger.info(f"[断言] {menu_item} 的表格组件已渲染")
        except PlaywrightTimeoutError:
            # 如果没找到表格，可能数据为空返回的空态骨架
            self.assertions.any_text_visible(["暂无数据", "没有匹配结果", "暂无记录", "共 0 条"])
            logger.info(f"[断言] {menu_item} 显示为空态，未发生崩溃")
            
        return self

    def fill_and_clear_menu_search_boundary(self) -> "ConsoleHomePage":
        """使用极端边界字符测试搜索框。"""
        boundary_value = "#'><script>alert(1)</script>"
        search_input = self.page.get_by_placeholder("请输入菜单名称").first
        try:
            search_input.wait_for(state="visible", timeout=3000)
        except PlaywrightTimeoutError:
            raise EntryNotExposed("控制台菜单搜索框未暴露，无法执行边界搜索探查") from None
            
        search_input.fill(boundary_value)
        assert search_input.input_value() == boundary_value, "边界字符未能成功填入"
        
        # 断言页面没有崩溃，且提示无数据
        self.assertions.any_text_visible(["无匹配", "暂无数据", "没有", "空"])
        
        search_input.clear()
        assert search_input.input_value() == "", "搜索框未能成功清空"
        logger.info("[边界测试] 侧边栏搜索边界值抗跌测试通过")
        return self

    def open_message_center(self) -> "ConsoleHomePage":
        """点击控制台通知/消息中心小铃铛。"""
        bell_icon = self.elements.find_candidates(
            [
                ("css", ".el-icon-bell"),
                ("css", "[class*='icon-bell']"),
                ("css", "[title='消息']"),
                ("css", "[title='通知']"),
                ("text", "消息"),
            ],
            description="消息中心图标",
            timeout=3000
        )
        if not bell_icon:
            raise EntryNotExposed("控制台消息中心入口未暴露")
            
        bell_icon.click()
        # 等待浮层或页面加载
        self.page.wait_for_timeout(1500)
        # 断言没有报系统错误
        self.assertions.page_not_blank_or_error()
        logger.info("[交互] 成功拉起消息通知中心")
        return self

    def switch_workbench_tab_and_assert(self) -> "ConsoleHomePage":
        """控制台内部切换 Tab 页签状态断言。"""
        tabs = self.page.locator(".el-tabs__item, .ant-tabs-tab").all()
        if not tabs or len(tabs) < 2:
            raise EntryNotExposed("控制台工作台未暴露足够的 Tab 页签")
            
        # 尝试点击第二个 Tab
        target_tab = tabs[1]
        tab_text = target_tab.inner_text()
        target_tab.click()
        self.nav.wait_ready()
        
        self.assertions.page_not_blank_or_error()
        logger.info(f"[断言] 成功切换多 Tab 页签: {tab_text}")
        return self
