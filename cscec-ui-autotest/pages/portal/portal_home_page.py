"""门户首页 — 登录后的主页面

提供从门户首页导航到各子模块（控制台、文档中心等）的能力。
"""

import re

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from core.base_page import BasePage
from core.logger import get_logger
from config.settings import settings

logger = get_logger("portal_home_page")


class PortalHomePage(BasePage):
    """门户首页（登录后的工作台）"""

    PAGE_NAME = "门户首页"

    def __init__(self, page: Page):
        super().__init__(page)

    # ── 导航到子模块 ──

    def open(self) -> "PortalHomePage":
        """打开门户首页"""
        self.nav.goto_url(settings.BASE_URL)
        return self

    def open_route(self, path: str) -> "PortalHomePage":
        """打开门户路由。"""
        if path == "/":
            url = settings.BASE_URL
        elif path.startswith("/"):
            url = f"{settings.BASE_URL.rstrip('/')}{path}"
        else:
            url = f"{settings.BASE_URL.rstrip('/')}/{path}"
        self.nav.goto_url(url)
        return self

    def navigate_to_console(self) -> "PortalHomePage":
        """导航到控制台"""
        self.elements.click_candidates(
            [
                ("text", "控制台"),
                ("css", "a[href*='console']"),
                ("css", ".menu-item:has-text('控制台')"),
            ],
            description="控制台入口",
        )
        self.nav.wait_ready()
        logger.info("[导航] → 控制台")
        return self

    def open_console_page(self) -> Page:
        """打开控制台新页签并返回新 Page。"""
        trigger = self._find_console_entry()
        try:
            with self.page.context.expect_page(timeout=settings.ACTION_TIMEOUT) as page_info:
                trigger.click()
            console_page = page_info.value
        except PlaywrightTimeoutError:
            console_page = self.page

        console_page.set_default_timeout(settings.DEFAULT_TIMEOUT)
        console_page.set_default_navigation_timeout(settings.NAVIGATION_TIMEOUT)
        console_page.wait_for_load_state("domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
        try:
            console_page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeoutError:
            pass

        console_page.get_by_text("控制台", exact=False).first.wait_for(
            state="visible",
            timeout=settings.ACTION_TIMEOUT,
        )
        logger.info("[导航] → 控制台新页签")
        return console_page

    def _find_console_entry(self) -> Locator:
        candidates = [
            self.page.locator(".kzt_wrap-iBP9KV").first,
            self.page.locator("div").filter(has_text=re.compile(r"^控制台$")).last,
            self.page.get_by_text("控制台", exact=True).last,
            self.page.locator("a:has-text('控制台')").first,
        ]
        for candidate in candidates:
            try:
                candidate.wait_for(state="visible", timeout=settings.DEFAULT_TIMEOUT)
                return candidate
            except PlaywrightTimeoutError:
                continue
        raise AssertionError("控制台入口不可见")

    def navigate_to_doc_center(self) -> "PortalHomePage":
        """导航到文档中心"""
        # 文档中心是独立 URL，直接跳转
        self.nav.goto_url(settings.DOC_CENTER_URL)
        logger.info("[导航] → 文档中心")
        return self

    # ── 通用导航 ──

    def click_menu_item(self, menu_name: str) -> "PortalHomePage":
        """点击菜单项"""
        self.elements.click_candidates(
            [
                ("text", menu_name),
                ("css", f".menu-item:has-text('{menu_name}')"),
                ("css", f"a:has-text('{menu_name}')"),
            ],
            description=f"菜单项: {menu_name}",
        )
        self.nav.wait_ready()
        return self

    def open_application(self, app_name: str) -> "PortalHomePage":
        """在工作台打开应用"""
        self.elements.click_candidates(
            [
                ("text", app_name),
                ("css", f".app-item:has-text('{app_name}')"),
                ("css", f"[title='{app_name}']"),
            ],
            description=f"应用: {app_name}",
        )
        self.nav.wait_ready()
        return self

    # ── 用户信息 ──

    def get_username_display(self) -> str:
        """获取页面显示的用户名"""
        try:
            user_el = self.page.locator(".user-info, .user-name, [class*='avatar']").first
            return user_el.inner_text()
        except Exception:
            return ""

    def logout(self) -> "PortalHomePage":
        """登出"""
        # 点击用户头像/名称
        self.elements.click_candidates(
            [
                ("css", ".user-info"),
                ("css", ".user-name"),
                ("css", "[class*='avatar']"),
            ],
            description="用户菜单",
        )
        # 点击退出
        self.elements.click_candidates(
            [
                ("text", "退出"),
                ("text", "登出"),
                ("text", "注销"),
            ],
            description="退出登录",
        )
        logger.info("[登出] 完成")
        return self

    # ── Assertions ──

    def should_be_logged_in(self) -> "PortalHomePage":
        """断言已登录状态"""
        # 登录后"登录"入口应不可见
        login_link = self.page.locator("text=登录").first
        is_login_visible = login_link.is_visible()
        assert not is_login_visible, "登录入口仍然可见，可能未登录成功"
        logger.info("[断言] 已处于登录状态")
        return self

    def should_be_readonly_page_ready(self, expected_texts: list[str]) -> "PortalHomePage":
        """断言门户只读页面可正常展示。"""
        self.assertions.page_not_blank_or_error()
        self.assertions.texts_visible(expected_texts)
        logger.info("[断言] 门户只读页面正常展示")
        return self

    def fill_and_clear_input(self, placeholder: str, value: str = "readonly-check") -> "PortalHomePage":
        """对门户页面的安全输入框执行填充和清空。"""
        search_input = self.page.get_by_placeholder(placeholder).first
        search_input.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        search_input.fill(value)
        assert search_input.input_value() == value, f"输入框未成功填充: {placeholder}"
        search_input.clear()
        assert search_input.input_value() == "", f"输入框未成功清空: {placeholder}"
        logger.info(f"[只读交互] 输入框填充清空: {placeholder}")
        return self
