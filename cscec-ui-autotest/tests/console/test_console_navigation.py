"""
控制台导航测试

测试场景：
- 控制台首页可访问
- 各子模块导航
"""

import pytest

from core.navigation_helpers import EntryNotExposed
from core.browser_health import BrowserHealthMonitor
from pages.console.console_global_navigation_page import ConsoleGlobalNavigationPage
from pages.portal.portal_home_page import PortalHomePage


@pytest.mark.console
@pytest.mark.readonly
class TestConsoleNavigation:
    """控制台导航测试"""

    @pytest.mark.smoke
    @pytest.mark.prod_mandatory
    def test_console_home_accessible(self, logged_in_page):
        """测试控制台首页可访问"""
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            "UI-BASE-CONSOLE-001",
            "控制台首页",
        ).start()
        try:
            ConsoleGlobalNavigationPage(logged_in_page).open_console_home()
        finally:
            health.stop()
        health.assert_healthy()

    @pytest.mark.regression
    def test_navigate_to_service_supply(self, logged_in_page):
        """测试导航到服务供给（入口未暴露则安全跳过）"""
        portal = PortalHomePage(logged_in_page)
        portal.open()
        console = portal.navigate_to_console()

        try:
            console.navigate_to_service_supply()
        except EntryNotExposed:
            pytest.skip(
                "服务供给入口在 UAT 未暴露，跳过（保留 registry needs_stabilization 标注）"
            )
        console.should_be_on_service_supply()
