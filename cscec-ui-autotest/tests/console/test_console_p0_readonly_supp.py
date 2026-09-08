"""PROD P0 控制台只读页面补充走查（第一阶段深水区探活）。"""

import pytest

from core.navigation_helpers import EntryNotExposed
from pages.console.console_home_page import ConsoleHomePage
from pages.portal.portal_home_page import PortalHomePage


def _open_console(logged_in_page) -> ConsoleHomePage:
    portal = PortalHomePage(logged_in_page)
    portal.open()
    console_page = portal.open_console_page()
    return ConsoleHomePage(console_page)


@pytest.mark.console
@pytest.mark.readonly
@pytest.mark.regression
class TestConsoleP0ReadonlySupp:
    """控制台 P0 补充只读探活。"""

    def test_console_supp_001_menu_drill_down_table_render(self, logged_in_page):
        """P0-CONSOLE-SUPP-001: 核心菜单的“点击贯穿”与表格渲染断言。
        相较于只看菜单是否存在，此用例穿透到二级页面并检查列表骨架加载。
        """
        console = _open_console(logged_in_page)
        # 选取配置管理下的租户参数，或者系统配置下的门户管理（高频且不易变）
        try:
            console.navigate_and_assert_table_renders(menu_group="系统配置", menu_item="门户管理")
        except EntryNotExposed as exc:
            pytest.skip(str(exc))

    def test_console_supp_002_workbench_tab_switching(self, logged_in_page):
        """P0-CONSOLE-SUPP-002: 多 Tab 页签保留状态测试。"""
        console = _open_console(logged_in_page)
        console.should_be_on_console()
        try:
            console.switch_workbench_tab_and_assert()
        except EntryNotExposed as exc:
            pytest.skip(str(exc))

    def test_console_supp_003_menu_search_boundary(self, logged_in_page):
        """P0-CONSOLE-SUPP-003: 侧边栏搜索边界值抗跌测试。
        输入乱码/脚本攻击字符串验证前端健壮性。
        """
        console = _open_console(logged_in_page)
        console.open_all_menu_view()
        try:
            console.fill_and_clear_menu_search_boundary()
        except EntryNotExposed as exc:
            pytest.skip(str(exc))

    def test_console_supp_004_notification_center(self, logged_in_page):
        """P0-CONSOLE-SUPP-004: 顶栏消息/通知中心加载验证。"""
        console = _open_console(logged_in_page)
        try:
            console.open_message_center()
        except EntryNotExposed as exc:
            pytest.skip(str(exc))
