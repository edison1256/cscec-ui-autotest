"""PROD console module entry regression checks."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from core.browser_health import BrowserHealthMonitor
from pages.console.console_global_navigation_page import ConsoleGlobalNavigationPage
from pages.console.console_workbench_page import ConsoleWorkbenchPage


PROFILE_COMMON_TOOL_CASES = [
    ("\u8d44\u6e90", "\u5e94\u7528\u7ba1\u7406", "C-P0-CONSOLE-PROFILE-002-resource-tool"),
    ("\u5ba1\u6279", "\u5f85\u529e\u6d41\u7a0b", "C-P0-CONSOLE-PROFILE-003-approval-tool"),
    ("\u8ba2\u5355", "\u8ba2\u5355\u7ba1\u7406", "C-P0-CONSOLE-PROFILE-004-order-tool"),
]
PROFILE_COMMON_TOOLS = [
    pytest.param(tool_text, expected_text, case_id.rsplit("-", 2)[0], id=case_id)
    for tool_text, expected_text, case_id in PROFILE_COMMON_TOOL_CASES
]

WORKBENCH_MODULE_ENTRIES = [
    pytest.param(
        "订单管理",
        "订单列表",
        r"/orderCenter/myOrders(?:[?]|$)",
        "C-P0-CONSOLE-WB-001",
        id="C-P0-CONSOLE-WB-001-order-management",
    ),
    pytest.param(
        "应用订阅",
        "应用列表",
        r"/subscription/app/appInfo(?:[?]|$)",
        "C-P0-CONSOLE-WB-002",
        id="C-P0-CONSOLE-WB-002-app-subscription",
    ),
    pytest.param(
        "数据资产订阅",
        "数据资产列表",
        r"/subscription/dataAssets(?:[?]|$)",
        "C-P0-CONSOLE-WB-003",
        id="C-P0-CONSOLE-WB-003-data-asset-subscription",
    ),
    pytest.param(
        "API订阅",
        "API列表",
        r"/subscription/apiResource(?:[?]|$)",
        "C-P0-CONSOLE-WB-004",
        id="C-P0-CONSOLE-WB-004-api-subscription",
    ),
    pytest.param(
        "组件订阅",
        "组件列表",
        r"/subscription/comp(?:[?]|$)",
        "C-P0-CONSOLE-WB-005",
        id="C-P0-CONSOLE-WB-005-component-subscription",
    ),
    pytest.param(
        "云产品订阅",
        "云产品列表",
        r"/subscription/cloud(?:[?]|$)",
        "C-P0-CONSOLE-WB-006",
        id="C-P0-CONSOLE-WB-006-cloud-product-subscription",
    ),
    pytest.param(
        "API资源",
        "API资源",
        r"/resource/apiResource(?:[?]|$)",
        "C-P0-CONSOLE-WB-007",
        id="C-P0-CONSOLE-WB-007-api-resource",
    ),
    pytest.param(
        "数据源配置",
        "数据源配置",
        r"/systemManage/dataSourceManage(?:[?]|$)",
        "C-P0-CONSOLE-WB-008",
        id="C-P0-CONSOLE-WB-008-data-source-config",
    ),
]

@dataclass(frozen=True)
class WorkbenchDetailCase:
    """One API-backed workbench detail interaction contract."""

    entry_text: str
    expected_title: str
    route_pattern: str
    list_api_pattern: str
    row_identity_field: str
    detail_identity_field: str
    required_labels: tuple[str, ...]
    case_id: str
    detail_api_pattern: str | None = None
    visible_identity_field: str | None = None


ORDER_DETAIL_LABELS = (
    "详情",
    "基础信息",
    "订单编码",
    "资源信息",
    "审批进度",
)

WORKBENCH_DETAIL_CASES = [
    pytest.param(
        WorkbenchDetailCase(
            entry_text="订单管理",
            expected_title="订单列表",
            route_pattern=r"/orderCenter/myOrders(?:[?]|$)",
            list_api_pattern=r"/irp-api/irp-portal-console/order/page$",
            row_identity_field="orderCode",
            detail_identity_field="id",
            required_labels=ORDER_DETAIL_LABELS,
            case_id="C-P0-CONSOLE-WB-DEEP-001",
            detail_api_pattern=r"/order/orderDetail[?]",
        ),
        id="C-P0-CONSOLE-WB-DEEP-001-order-detail",
    ),
    pytest.param(
        WorkbenchDetailCase(
            entry_text="应用订阅",
            expected_title="应用列表",
            route_pattern=r"/subscription/app/appInfo(?:[?]|$)",
            list_api_pattern=(
                r"/irp-api/irp-portal-console/console/rsc/app/"
                r"apply/history/list$"
            ),
            row_identity_field="id",
            detail_identity_field="orderId",
            required_labels=ORDER_DETAIL_LABELS,
            case_id="C-P0-CONSOLE-WB-DEEP-002",
            detail_api_pattern=r"/order/orderDetail[?]",
        ),
        id="C-P0-CONSOLE-WB-DEEP-002-app-subscription-detail",
    ),
    pytest.param(
        WorkbenchDetailCase(
            entry_text="数据资产订阅",
            expected_title="数据资产列表",
            route_pattern=r"/subscription/dataAssets(?:[?]|$)",
            list_api_pattern=(
                r"/irp-api/irp-portal-console/workbench/rsc/data/"
                r"apply/history/list$"
            ),
            row_identity_field="id",
            detail_identity_field="orderId",
            required_labels=ORDER_DETAIL_LABELS + ("资产列表",),
            case_id="C-P0-CONSOLE-WB-DEEP-003",
            detail_api_pattern=r"/order/orderDetail[?]",
            visible_identity_field="rscName",
        ),
        id="C-P0-CONSOLE-WB-DEEP-003-data-asset-subscription-detail",
    ),
    pytest.param(
        WorkbenchDetailCase(
            entry_text="组件订阅",
            expected_title="组件列表",
            route_pattern=r"/subscription/comp(?:[?]|$)",
            list_api_pattern=(
                r"/irp-api/irp-portal-console/console/rsc/compt/"
                r"apply/history/list$"
            ),
            row_identity_field="id",
            detail_identity_field="orderId",
            required_labels=("详情", "订单ID"),
            case_id="C-P0-CONSOLE-WB-DEEP-004",
            visible_identity_field="orderId",
        ),
        id="C-P0-CONSOLE-WB-DEEP-004-component-subscription-detail",
    ),
    pytest.param(
        WorkbenchDetailCase(
            entry_text="云产品订阅",
            expected_title="云产品列表",
            route_pattern=r"/subscription/cloud(?:[?]|$)",
            list_api_pattern=r"/irp-api/irp-portal-console/cloud/applyList$",
            row_identity_field="id",
            detail_identity_field="orderId",
            required_labels=ORDER_DETAIL_LABELS,
            case_id="C-P0-CONSOLE-WB-DEEP-005",
            detail_api_pattern=r"/order/orderDetail[?]",
        ),
        id="C-P0-CONSOLE-WB-DEEP-005-cloud-product-subscription-detail",
    ),
]


@pytest.mark.console
@pytest.mark.smoke
@pytest.mark.readonly
@pytest.mark.regression
@pytest.mark.domain_split
class TestConsoleWorkbenchModuleEntries:
    """控制台常用模块入口只读回归。"""

    @pytest.mark.parametrize(
        "entry_text, expected_text, route_pattern, case_id",
        WORKBENCH_MODULE_ENTRIES,
    )
    @pytest.mark.prod_conditional
    def test_workbench_module_entry_opens_without_error(
        self,
        logged_in_page,
        require_case_prerequisite,
        entry_text: str,
        expected_text: str,
        route_pattern: str,
        case_id: str,
    ) -> None:
        """Open one configured card and require its target business response."""
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            case_id,
            f"控制台工作台入口 {entry_text}",
        ).start()
        try:
            workbench = ConsoleWorkbenchPage(logged_in_page).open()
            require_case_prerequisite(
                case_id,
                workbench.module_prerequisite(entry_text),
                health_monitor=health,
            )
            workbench.open_module(entry_text, expected_text, route_pattern)
        finally:
            health.stop()
        health.assert_healthy()

    @pytest.mark.parametrize("detail_case", WORKBENCH_DETAIL_CASES)
    @pytest.mark.prod_conditional
    def test_workbench_module_first_detail_opens_without_error(
        self,
        logged_in_page,
        require_case_prerequisite,
        detail_case: WorkbenchDetailCase,
    ) -> None:
        """Open the first API record's exact row and validate its detail."""
        workbench = ConsoleWorkbenchPage(logged_in_page).open()
        require_case_prerequisite(
            detail_case.case_id,
            workbench.module_prerequisite(detail_case.entry_text),
        )
        snapshot = workbench.open_module_with_list_snapshot(
            detail_case.entry_text,
            detail_case.expected_title,
            detail_case.route_pattern,
            detail_case.list_api_pattern,
        )
        require_case_prerequisite(
            detail_case.case_id,
            workbench.detail_prerequisite(snapshot),
        )

        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            detail_case.case_id,
            f"{detail_case.entry_text} 首条详情",
        ).start()
        try:
            workbench.open_first_detail(
                snapshot,
                row_identity_field=detail_case.row_identity_field,
                detail_identity_field=detail_case.detail_identity_field,
                required_labels=detail_case.required_labels,
                detail_api_pattern=detail_case.detail_api_pattern,
                visible_identity_field=detail_case.visible_identity_field,
            )
        finally:
            health.stop()
        health.assert_healthy()

    @pytest.mark.parametrize("tool_text, expected_text, case_id", PROFILE_COMMON_TOOLS)
    @pytest.mark.prod_mandatory
    def test_console_profile_common_tool_opens_without_error(
        self,
        logged_in_page,
        tool_text,
        expected_text,
        case_id,
    ):
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            case_id,
            f"账号浮层常用工具 {tool_text}",
        ).start()
        try:
            console = ConsoleGlobalNavigationPage(logged_in_page).open_console_home()
            console.open_profile_tool(tool_text, expected_text)
        finally:
            health.stop()
        health.assert_healthy()

    @pytest.mark.prod_mandatory
    def test_console_topbar_return_to_portal_opens_without_error(self, logged_in_page):
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            "C-P0-CONSOLE-TOPBAR-001",
            "控制台顶部返回门户",
        ).start()
        try:
            console = ConsoleGlobalNavigationPage(logged_in_page).open_console_home()
            console.return_to_portal()
        finally:
            health.stop()
        health.assert_healthy()
