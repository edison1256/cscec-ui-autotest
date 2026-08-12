"""
登录模块 fixtures

提供登录模块特定的测试 fixtures：
- 登录页面 Page Object
- 测试用户数据
- 登录态管理
"""

import pytest

from pages.portal.login_page import LoginPage
from pages.portal.portal_home_page import PortalHomePage
from utils.data_loader import get_case_data, get_parametrize_data


# ────────────────────── Page Object Fixtures ──────────────────────

@pytest.fixture(scope="function")
def login_page(fresh_page):
    """登录页 Page Object（使用独立 context）"""
    return LoginPage(fresh_page)


@pytest.fixture(scope="function")
def portal(logged_in_page):
    """门户首页 Page Object（已登录状态）"""
    return PortalHomePage(logged_in_page)


# ────────────────────── 测试数据 Fixtures ──────────────────────

@pytest.fixture(scope="module")
def login_data():
    """登录模块测试数据"""
    return get_case_data("login", "login_success")


@pytest.fixture(scope="module")
def login_failure_cases():
    """登录失败测试用例数据（参数化）"""
    return get_parametrize_data("login", "login_failure", "cases")


@pytest.fixture(scope="module")
def users_data():
    """用户数据"""
    return get_case_data("login", "users")


# ────────────────────── 测试步骤 Fixtures ──────────────────────

@pytest.fixture(scope="function")
def fresh_login(login_page, login_data):
    """
    执行登录并返回登录页对象

    使用场景：需要测试登录后状态的用例
    """
    login_page.login(
        username=login_data.get("username"),
        password=login_data.get("password")
    )
    return login_page
