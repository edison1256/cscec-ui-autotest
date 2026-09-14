"""Strict production console shell, profile, and top-bar interactions."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from playwright.sync_api import Locator, Page, expect

from config.settings import settings
from core.base_page import BasePage
from core.interaction_evidence import click_and_expect, require_actionable
from core.logger import get_logger


logger = get_logger("console_global_navigation_page")


class ConsoleGlobalNavigationPage(BasePage):
    """Operate stable global controls on the split-domain console."""

    def open_console_home(self) -> "ConsoleGlobalNavigationPage":
        """Open the console shell and require its stable workbench landmarks."""
        self.page.goto(
            settings.CONSOLE_BASE_URL,
            wait_until="domcontentloaded",
            timeout=settings.NAVIGATION_TIMEOUT,
        )
        expect(self.page).to_have_url(
            re.compile(rf"^https?://{re.escape(self._console_host())}/"),
            timeout=settings.NAVIGATION_TIMEOUT,
        )
        expect(self.page.get_by_text("控制台", exact=True).first).to_be_visible(
            timeout=settings.NAVIGATION_TIMEOUT
        )
        expect(self.page.get_by_text("工作台", exact=True).first).to_be_visible()
        self.assertions.page_not_blank_or_error()
        logger.info("[导航] 控制台工作台严格就绪")
        return self

    def verify_menu_search_round_trip(
        self,
        value: str = "readonly-check",
    ) -> "ConsoleGlobalNavigationPage":
        """Fill and clear the visible menu search without soft fallback."""
        search = self.page.get_by_placeholder("请输入菜单名称", exact=True)
        require_actionable(search, "控制台菜单搜索")
        search.fill(value)
        expect(search).to_have_value(value)
        search.clear()
        expect(search).to_have_value("")
        logger.info("[只读交互] 控制台菜单搜索填充并清空")
        return self

    def open_profile_tool(
        self,
        tool_text: str,
        expected_text: str,
    ) -> "ConsoleGlobalNavigationPage":
        """Open one current profile-popover tool and prove its destination."""
        self._open_profile_popover()
        tool = self.page.locator(".tool-item").filter(
            has=self.page.get_by_text(tool_text, exact=True)
        ).first

        before_url = self.page.url

        def destination_ready() -> None:
            expect(self.page).to_have_url(
                re.compile(rf"^https?://{re.escape(self._console_host())}/")
            )
            expect(self.page.get_by_text(expected_text, exact=False).first).to_be_visible(
                timeout=settings.ACTION_TIMEOUT
            )

        click_and_expect(tool, destination_ready, action_name=f"账号浮层常用工具 {tool_text}")
        assert self.page.url != before_url, (
            f"账号浮层常用工具 {tool_text}: 点击后 URL 未变化: {self.page.url}"
        )
        self.assertions.page_not_blank_or_error()
        logger.info(f"[只读交互] 账号浮层常用工具: {tool_text}")
        return self

    def return_to_portal(self) -> "ConsoleGlobalNavigationPage":
        """Use the visible rollback icon and require the cloud portal host."""
        rollback = self.page.locator('[role="img"][aria-label="rollback"]').last

        def portal_ready() -> None:
            expect(self.page).to_have_url(
                re.compile(rf"^https?://{re.escape(self._portal_host())}/"),
                timeout=settings.NAVIGATION_TIMEOUT,
            )
            expect(self.page.locator("body")).not_to_be_empty()

        click_and_expect(rollback, portal_ready, action_name="控制台顶部返回门户")
        self.assertions.page_not_blank_or_error()
        logger.info("[导航] 控制台顶部返回 cloud 门户")
        return self

    def _open_profile_popover(self) -> Locator:
        trigger = self.page.locator('[class*="userButton"]').first

        def popover_ready() -> None:
            expect(self.page.get_by_text("账号信息", exact=True)).to_be_visible()
            expect(self.page.get_by_text("常用工具", exact=True)).to_be_visible()

        require_actionable(trigger, "控制台账号信息入口").hover()
        popover_ready()
        return trigger

    @staticmethod
    def _console_host() -> str:
        return urlparse(settings.CONSOLE_BASE_URL).netloc.lower()

    @staticmethod
    def _portal_host() -> str:
        return urlparse(settings.PORTAL_BASE_URL).netloc.lower()
