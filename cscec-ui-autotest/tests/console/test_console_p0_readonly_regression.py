"""PROD P0 控制台只读页面回归。"""

import pytest

from core.browser_health import BrowserHealthMonitor
from pages.console.console_global_navigation_page import ConsoleGlobalNavigationPage
from pages.console.console_menu_page import ConsoleMenuPage


CONSOLE_MENU_GROUPS = [
    pytest.param(
        "订阅服务",
        "C-P0-CONSOLE-003",
        id="C-P0-CONSOLE-003-subscription-service",
    ),
    pytest.param(
        "审批流程",
        "C-P0-CONSOLE-004",
        id="C-P0-CONSOLE-004-approval-flow",
    ),
    pytest.param(
        "订单中心",
        "C-P0-CONSOLE-005",
        id="C-P0-CONSOLE-005-order-center",
    ),
    pytest.param(
        "工单中心",
        "C-P0-CONSOLE-006",
        id="C-P0-CONSOLE-006-ticket-center",
    ),
    pytest.param(
        "评价中心",
        "C-P0-CONSOLE-007",
        id="C-P0-CONSOLE-007-evaluation-center",
    ),
    pytest.param(
        "系统配置",
        "C-P0-CONSOLE-008",
        id="C-P0-CONSOLE-008-system-config",
    ),
    pytest.param(
        "计量统计",
        "C-P0-CONSOLE-009",
        id="C-P0-CONSOLE-009-metering-statistics",
    ),
    pytest.param(
        "运维监控",
        "C-P0-CONSOLE-010",
        id="C-P0-CONSOLE-010-ops-monitoring",
    ),
    pytest.param(
        "运营管理",
        "C-P0-CONSOLE-011",
        id="C-P0-CONSOLE-011-operation-management",
    ),
    pytest.param(
        "权限管理",
        "C-P0-CONSOLE-012",
        id="C-P0-CONSOLE-012-permission-management",
    ),
]


@pytest.mark.console
@pytest.mark.smoke
@pytest.mark.readonly
@pytest.mark.regression
class TestConsoleP0ReadonlyRegression:
    """控制台 P0 只读页面回归。"""

    @pytest.mark.prod_mandatory
    def test_console_workbench_accessible_and_search_safe(self, logged_in_page):
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            "C-P0-CONSOLE-001",
            "控制台工作台菜单搜索",
        ).start()
        try:
            console = ConsoleGlobalNavigationPage(logged_in_page).open_console_home()
            console.verify_menu_search_round_trip()
        finally:
            health.stop()
        health.assert_healthy()

    @pytest.mark.prod_conditional
    def test_console_all_menu_view_accessible(
        self,
        logged_in_page,
        require_case_prerequisite,
    ) -> None:
        """C-P0-CONSOLE-002: API-authorized top-level menus render."""
        case_id = "C-P0-CONSOLE-002"
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            case_id,
            "控制台授权菜单树",
        ).start()
        try:
            console = ConsoleMenuPage(logged_in_page).open_console_home()
            require_case_prerequisite(
                case_id,
                console.menu_tree_prerequisite(),
                health_monitor=health,
            )
            console.verify_menu_tree_rendered().verify_menu_search_round_trip()
        finally:
            health.stop()
        health.assert_healthy()

    @pytest.mark.parametrize("group_name, case_id", CONSOLE_MENU_GROUPS)
    @pytest.mark.prod_conditional
    def test_console_p0_menu_group_visible(
        self,
        logged_in_page,
        require_case_prerequisite,
        group_name: str,
        case_id: str,
    ) -> None:
        """Expand an authorized menu group and verify its direct children."""
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            case_id,
            f"控制台菜单组 {group_name}",
        ).start()
        try:
            console = ConsoleMenuPage(logged_in_page).open_console_home()
            require_case_prerequisite(
                case_id,
                console.top_level_menu_prerequisite(group_name),
                health_monitor=health,
            )
            console.expand_menu_group(group_name)
        finally:
            health.stop()
        health.assert_healthy()

    @pytest.mark.prod_conditional
    def test_console_flow_page_accessible(
        self,
        logged_in_page,
        require_case_prerequisite,
    ) -> None:
        """C-P0-CONSOLE-013: open the authorized flow entry from the sidebar."""
        case_id = "C-P0-CONSOLE-013"
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            case_id,
            "控制台流程入口",
        ).start()
        try:
            console = ConsoleMenuPage(logged_in_page).open_console_home()
            require_case_prerequisite(
                case_id,
                console.top_level_menu_prerequisite("流程"),
                health_monitor=health,
            )
            console.open_flow_page()
        finally:
            health.stop()
        health.assert_healthy()
