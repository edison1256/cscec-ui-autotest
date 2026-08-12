"""
登录异常场景测试

测试场景：
- 错误密码登录
- 空凭证登录
"""

import pytest

from pages.portal.login_page import LoginPage
from config.settings import settings


@pytest.mark.login
@pytest.mark.regression
@pytest.mark.readonly
class TestLoginFailure:
    """登录异常场景测试"""

    def test_login_with_wrong_password(self, fresh_page):
        """测试错误密码登录"""
        login_page = LoginPage(fresh_page)
        login_page.open()
        login_page.click_login_entry()
        login_page.fill_credentials(
            username=settings.USERNAME,
            password="WRONG_PASSWORD_123456",
        )
        login_page.click_login_button()
        login_page.should_login_fail()

    def test_login_with_empty_credentials(self, fresh_page):
        """测试空凭证登录"""
        login_page = LoginPage(fresh_page)
        login_page.open()
        login_page.click_login_entry()
        login_page.fill_credentials(username="", password="")
        login_page.click_login_button()
        login_page.should_login_fail()
