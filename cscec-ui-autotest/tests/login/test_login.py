"""
登录流程测试

测试场景：
- 正常登录/登出
- 会话过期处理
"""

import pytest

from pages.portal.login_page import LoginPage
from pages.portal.portal_home_page import PortalHomePage
from config.settings import settings
from core.logger import get_logger

logger = get_logger("test_login")


@pytest.mark.login
class TestLogin:
    """登录流程测试"""

    @pytest.mark.smoke
    @pytest.mark.readonly
    def test_login_success(self, fresh_page):
        """测试正常登录流程"""
        login_page = LoginPage(fresh_page)
        login_page.login()
        login_page.should_login_succeed()

    @pytest.mark.smoke
    @pytest.mark.readonly
    def test_portal_homepage_accessible(self, logged_in_page):
        """测试登录后门户首页可访问"""
        portal = PortalHomePage(logged_in_page)
        portal.open()
        portal.should_be_logged_in()

    @pytest.mark.regression
    @pytest.mark.readonly
    def test_logout(self, fresh_page):
        """测试登出流程"""
        login_page = LoginPage(fresh_page)
        login_page.login()

        portal = PortalHomePage(fresh_page)
        portal.logout()
        fresh_page.wait_for_selector("text=登录", timeout=settings.ACTION_TIMEOUT)
        logger.info("[断言] 登出成功")
