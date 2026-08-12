"""
控制台模块 fixtures

提供控制台模块特定的测试 fixtures：
- 控制台页面 Page Object
- 导航测试数据
- 服务供给/项目管理相关 fixtures
"""

import pytest

from pages.console.console_home_page import ConsoleHomePage
from utils.data_loader import get_case_data, get_parametrize_data


# ────────────────────── Page Object Fixtures ──────────────────────

@pytest.fixture(scope="function")
def console(logged_in_page):
    """控制台首页 Page Object"""
    return ConsoleHomePage(logged_in_page)


# ────────────────────── 测试数据 Fixtures ──────────────────────

@pytest.fixture(scope="module")
def navigation_data():
    """导航测试数据"""
    return get_case_data("console", "navigation")


@pytest.fixture(scope="module")
def service_supply_data():
    """服务供给测试数据"""
    return get_case_data("console", "service_supply")


@pytest.fixture(scope="module")
def project_management_data():
    """项目管理测试数据"""
    return get_case_data("console", "project_management")


# ────────────────────── 导航 Fixtures ──────────────────────

@pytest.fixture(scope="function")
def at_service_supply(console):
    """导航到服务供给页面"""
    console.nav.goto_path("/console")
    console.navigate_to_service_supply()
    return console


@pytest.fixture(scope="function")
def at_project_mgmt(console):
    """导航到项目管理页面"""
    console.nav.goto_path("/console")
    console.navigate_to_project_mgmt()
    return console


@pytest.fixture(scope="function")
def at_process_mgmt(console):
    """导航到流程管理页面"""
    console.nav.goto_path("/console")
    console.navigate_to_process_mgmt()
    return console


# ────────────────────── 参数化数据 Fixtures ──────────────────────

@pytest.fixture(scope="module")
def menu_items():
    """菜单项参数化数据"""
    return get_parametrize_data("console", "navigation", "menu_items")
