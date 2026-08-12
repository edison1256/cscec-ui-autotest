"""
控制台导航测试

测试场景：
- 控制台首页可访问
- 各子模块导航
"""

import pytest

from pages.portal.portal_home_page import PortalHomePage
from pages.console.console_home_page import ConsoleHomePage


@pytest.mark.console
@pytest.mark.readonly
class TestConsoleNavigation:
    """控制台导航测试"""

    @pytest.mark.smoke
    def test_console_home_accessible(self, logged_in_page):
        """测试控制台首页可访问"""
        portal = PortalHomePage(logged_in_page)
        portal.open()
        portal.navigate_to_console()

        console = ConsoleHomePage(logged_in_page)
        console.should_be_on_console()

    @pytest.mark.regression
    def test_navigate_to_service_supply(self, logged_in_page):
        """测试导航到服务供给"""
        portal = PortalHomePage(logged_in_page)
        portal.open()
        portal.navigate_to_console()

        console = ConsoleHomePage(logged_in_page)
        console.navigate_to_service_supply()
        console.nav.wait_for_url_contains("service")
        console.assertions.any_text_visible(["服务供给", "服务列表"])
