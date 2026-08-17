"""
控制台导航测试

测试场景：
- 控制台首页可访问
- 各子模块导航
"""

import pytest

from core.navigation_helpers import EntryNotExposed
from pages.portal.portal_home_page import PortalHomePage


@pytest.mark.console
@pytest.mark.readonly
class TestConsoleNavigation:
    """控制台导航测试"""

    @pytest.mark.smoke
    def test_console_home_accessible(self, logged_in_page):
        """测试控制台首页可访问"""
        portal = PortalHomePage(logged_in_page)
        portal.open()
        console = portal.navigate_to_console()
        console.should_be_on_console()

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
