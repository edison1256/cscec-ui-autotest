"""PROD P0 控制台只读页面回归。"""

import pytest

from core.navigation_helpers import EntryNotExposed
from pages.console.console_home_page import ConsoleHomePage
from pages.portal.portal_home_page import PortalHomePage


CONSOLE_MENU_GROUPS = [
    pytest.param(
        "订阅服务",
        ["应用列表", "云产品列表", "API列表", "组件列表", "数据资产列表"],
        id="C-P0-CONSOLE-003-subscription-service",
    ),
    pytest.param(
        "审批流程",
        ["流程管理", "流程监控", "审批中心"],
        id="C-P0-CONSOLE-004-approval-flow",
    ),
    pytest.param(
        "订单中心",
        ["订单管理"],
        id="C-P0-CONSOLE-005-order-center",
    ),
    pytest.param(
        "工单中心",
        ["工单管理"],
        id="C-P0-CONSOLE-006-ticket-center",
    ),
    pytest.param(
        "评价中心",
        ["评价数据管理"],
        id="C-P0-CONSOLE-007-evaluation-center",
    ),
    pytest.param(
        "系统配置",
        ["门户管理", "资源配置", "厂商管理", "巡检配置", "日志审计查询", "工单配置"],
        id="C-P0-CONSOLE-008-system-config",
    ),
    pytest.param(
        "计量统计",
        ["租户的资源", "租户的订阅"],
        id="C-P0-CONSOLE-009-metering-statistics",
    ),
    pytest.param(
        "运维监控",
        ["运维指标", "运维巡检"],
        id="C-P0-CONSOLE-010-ops-monitoring",
    ),
    pytest.param(
        "运营管理",
        ["运营报表", "消息推送"],
        id="C-P0-CONSOLE-011-operation-management",
    ),
    pytest.param(
        "权限管理",
        ["登录管理", "用户管理", "租户管理", "角色管理"],
        id="C-P0-CONSOLE-012-permission-management",
    ),
]


def _open_console(logged_in_page) -> ConsoleHomePage:
    portal = PortalHomePage(logged_in_page)
    portal.open()
    console_page = portal.open_console_page()
    return ConsoleHomePage(console_page)


@pytest.mark.console
@pytest.mark.smoke
@pytest.mark.readonly
@pytest.mark.regression
class TestConsoleP0ReadonlyRegression:
    """控制台 P0 只读页面回归。"""

    def test_console_workbench_accessible_and_search_safe(self, logged_in_page):
        console = _open_console(logged_in_page)
        console.should_be_on_console()
        console.should_be_readonly_page_ready(["常用模块"])
        console.fill_and_clear_menu_search()

    def test_console_all_menu_view_accessible(self, logged_in_page):
        console = _open_console(logged_in_page)
        console.open_all_menu_view()
        console.should_be_readonly_page_ready(["常用模块"])
        console.fill_and_clear_menu_search()

    @pytest.mark.parametrize("group_name, item_names", CONSOLE_MENU_GROUPS)
    def test_console_p0_menu_group_visible(self, logged_in_page, group_name, item_names):
        console = _open_console(logged_in_page)
        console.open_all_menu_view()
        try:
            console.should_show_menu_group(group_name, item_names)
        except EntryNotExposed as exc:
            pytest.skip(str(exc))
        console.fill_and_clear_menu_search()

    def test_console_flow_page_accessible(self, logged_in_page):
        console = _open_console(logged_in_page)
        try:
            console.navigate_to_flow_page()
        except EntryNotExposed as exc:
            pytest.skip(str(exc))
        console.should_be_readonly_page_ready(["流程"])
        console.fill_and_clear_menu_search()
