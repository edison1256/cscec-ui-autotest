"""门户首页 — 登录后的主页面

提供从门户首页导航到各子模块（控制台、文档中心等）的能力。
"""

import re
import json
from urllib.parse import urlparse

from playwright.sync_api import FrameLocator, Locator, Page, TimeoutError as PlaywrightTimeoutError

from core.base_page import BasePage
from core.logger import get_logger
from config.settings import settings

logger = get_logger("portal_home_page")

CONSOLE_WORKBENCH_ROUTE = "/udpweb/portal/index.html#/portal/home/workbench?suitKey=portal"


class PortalHomePage(BasePage):
    """门户首页（登录后的工作台）"""

    PAGE_NAME = "门户首页"

    def __init__(self, page: Page):
        super().__init__(page)

    # ── 导航到子模块 ──

    def open(self) -> "PortalHomePage":
        """打开门户首页"""
        self.nav.goto_url(settings.PORTAL_BASE_URL)
        return self

    def open_route(self, path: str) -> "PortalHomePage":
        """打开门户路由。"""
        if path == "/":
            url = settings.PORTAL_BASE_URL
        elif path.startswith("/#/"):
            portal_host = urlparse(settings.PORTAL_BASE_URL).netloc.lower()
            if portal_host.startswith("cloud"):
                url = f"{settings.PORTAL_BASE_URL.rstrip('/')}/{path[1:]}"
            else:
                url = f"{settings.PORTAL_BASE_URL.rstrip('/')}/udpweb/portal/index.html{path[1:]}"
        elif path.startswith("/"):
            url = f"{settings.PORTAL_BASE_URL.rstrip('/')}{path}"
        else:
            url = f"{settings.PORTAL_BASE_URL.rstrip('/')}/{path}"
        self.nav.goto_url(url)
        return self

    def open_workbench(self) -> "PortalHomePage":
        """打开工作台首页。"""
        self.nav.goto_url(settings.WORKBENCH_BASE_URL)
        return self

    def navigate_to_console(self) -> "ConsoleHomePage":
        """导航到控制台（中建云管理后台）。

        域名拆分后，控制台与门户/工作台可能不再共用同一 host。优先直达
        ``CONSOLE_BASE_URL`` 下的控制台工作台；若环境未开放直链，再回退到门户
        页面入口探测。
        """
        from pages.console.console_home_page import ConsoleHomePage

        return ConsoleHomePage(self.open_console_page())

    def open_console_page(self) -> Page:
        """打开控制台页面并返回 Page。"""
        try:
            console_page = self._open_console_direct_page()
            logger.info("[导航] → 控制台直达页签")
            return console_page
        except Exception as exc:
            logger.warning(f"[导航] 控制台直达失败，回退门户入口: {exc}")

        console_page = self._open_console_from_portal_entry()
        logger.info("[导航] → 控制台入口页签")
        return console_page

    def _open_console_direct_page(self) -> Page:
        """Open the split console workbench directly in a new page."""
        console_page = self.page.context.new_page()
        console_page.set_default_timeout(settings.DEFAULT_TIMEOUT)
        console_page.set_default_navigation_timeout(settings.NAVIGATION_TIMEOUT)
        try:
            console_page.goto(
                settings.console_url(CONSOLE_WORKBENCH_ROUTE),
                timeout=settings.NAVIGATION_TIMEOUT,
                wait_until="domcontentloaded",
            )
            self._wait_console_page_ready(console_page)
            return console_page
        except Exception:
            if not console_page.is_closed():
                console_page.close()
            raise

    def _open_console_from_portal_entry(self) -> Page:
        """Fallback: open console from the visible portal entry."""
        page = self.page
        new_pages: list = []

        try:
            # 优先判断“管理后台”下拉入口（UAT 门户形态）
            mgr = self.elements.find_candidates(
                [
                    ("text", "管理后台"),
                    ("css", "a:has-text('管理后台')"),
                ],
                description="管理后台入口",
                timeout=2500,
            )
            if mgr:
                try:
                    mgr.hover()
                except PlaywrightTimeoutError:
                    mgr.click()
                self.nav.wait_ready()
                trigger = self.elements.find_candidates(
                    [
                        ("text", "控制台"),
                        ("css", "a:has-text('控制台')"),
                    ],
                    description="控制台入口（下拉内）",
                    timeout=4000,
                )
                if not trigger:
                    raise AssertionError("管理后台下拉中未找到“控制台”入口")
                try:
                    with page.context.expect_page(timeout=8000) as info:
                        trigger.click()
                    new_pages.append(info.value)
                except PlaywrightTimeoutError:
                    pass  # 同页跳转兜底
            else:
                # 旧环境/直接入口：直接点击“控制台”
                try:
                    with page.context.expect_page(timeout=5000) as info:
                        self.elements.click_candidates(
                            [
                                ("text", "控制台"),
                                ("css", "a[href*='console']"),
                                ("css", ".menu-item:has-text('控制台')"),
                            ],
                            description="控制台入口",
                        )
                    new_pages.append(info.value)
                except PlaywrightTimeoutError:
                    pass  # 同页跳转兜底
        except PlaywrightTimeoutError:
            # 入口探测极端超时，交由下方 readiness 校验兜底
            pass

        self.nav.wait_ready()
        target = new_pages[0] if new_pages else page
        target.wait_for_load_state("domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
        try:
            target.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeoutError:
            pass
        target.get_by_text("控制台", exact=False).first.wait_for(
            state="visible", timeout=settings.ACTION_TIMEOUT
        )
        return target

    def _wait_console_page_ready(self, console_page: Page) -> None:
        console_page.wait_for_load_state("domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
        try:
            console_page.wait_for_load_state("networkidle", timeout=15000)
        except PlaywrightTimeoutError:
            pass

        body_text = console_page.locator("body").inner_text(timeout=settings.ACTION_TIMEOUT)
        if any(text in body_text for text in ("控制台", "工作台", "常用模块", "应用资源")):
            return
        raise AssertionError(f"控制台工作台未就绪，当前 URL={console_page.url}")

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
            login_info = self.page.evaluate("window.localStorage.getItem('__login_info__')")
            if login_info:
                data = json.loads(login_info)
                return data.get("userName") or data.get("userNo") or ""
        except Exception:
            pass
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
        login_info = self.page.evaluate("window.localStorage.getItem('__login_info__')")
        if not login_info:
            self.assertions.any_text_visible(["工作台", "中建云", "常用模块"])
        logger.info("[断言] 已处于登录状态")
        return self

    def should_be_readonly_page_ready(self, expected_texts: list[str]) -> "PortalHomePage":
        """断言门户只读页面可正常展示。"""
        self.assertions.page_not_blank_or_error()
        self.assertions.texts_visible(expected_texts)
        logger.info("[断言] 门户只读页面正常展示")
        return self

    def should_be_on_portal_domain(self) -> "PortalHomePage":
        """断言当前页面使用门户域名。"""
        expected = urlparse(settings.PORTAL_BASE_URL).netloc.lower()
        current = urlparse(self.page.url).netloc.lower()
        assert current == expected, f"当前页面未使用门户域名，expected={expected}, actual={current}, url={self.page.url}"
        logger.info(f"[断言] 当前页面使用门户域名: {expected}")
        return self

    def should_not_have_console_domain_links(self, link_texts: list[str]) -> "PortalHomePage":
        """断言指定链接文本不再指向控制台域名。"""
        console_host = urlparse(settings.CONSOLE_BASE_URL).netloc.lower()
        offenders: list[str] = []
        for text in link_texts:
            link = self.page.get_by_role("link", name=re.compile(re.escape(text))).first
            try:
                link.wait_for(state="visible", timeout=2000)
            except PlaywrightTimeoutError:
                continue
            href = link.get_attribute("href") or ""
            if console_host and console_host in href.lower():
                offenders.append(f"{text}: {href}")
        assert not offenders, "以下门户链接仍指向控制台域名: " + "; ".join(offenders)
        logger.info("[断言] 门户链接未指向控制台域名")
        return self

    def should_show_any_module(self, module_names: list[str]) -> "PortalHomePage":
        """断言至少一个期望门户模块可见。"""
        self.assertions.any_text_visible(module_names)
        return self

    def click_first_visible_link(self, names: list[str]) -> Page:
        """点击第一个可见链接，并返回跳转后的页面。"""
        for name in names:
            link = self.page.get_by_role("link", name=re.compile(re.escape(name))).first
            try:
                link.wait_for(state="visible", timeout=2500)
            except PlaywrightTimeoutError:
                continue
            try:
                with self.page.context.expect_page(timeout=5000) as page_info:
                    link.click()
                target = page_info.value
            except PlaywrightTimeoutError:
                target = self.page
            target.wait_for_load_state("domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
            return target
        raise AssertionError(f"未找到可点击链接: {names}")

    def first_available_frame(self) -> FrameLocator | None:
        """返回页面中的第一个 iframe。"""
        frame = self.page.locator("iframe").first
        try:
            frame.wait_for(state="attached", timeout=5000)
        except PlaywrightTimeoutError:
            return None
        return self.page.frame_locator("iframe").first

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
