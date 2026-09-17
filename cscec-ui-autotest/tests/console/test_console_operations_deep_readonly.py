"""Batch G candidates for operations monitoring and management pages."""

from __future__ import annotations

import pytest

from core.browser_health import BrowserHealthMonitor
from pages.console.operation_management_page import OperationManagementPage
from pages.console.operations_monitoring_page import OperationsMonitoringPage


pytestmark = [
    pytest.mark.console,
    pytest.mark.readonly,
    pytest.mark.regression,
    pytest.mark.domain_split,
]


class TestConsoleOperationsDeepReadonly:
    """Validate every authorized Batch G leaf through the real menu tree."""

    @pytest.mark.parametrize(
        ("case_id", "page_class", "method_name", "action_name"),
        [
            ("OPS-CAPACITY-001", OperationsMonitoringPage, "open_capacity_index", "容量指标只读探查"),
            ("OPS-PERFORMANCE-001", OperationsMonitoringPage, "open_performance_index", "性能指标只读探查"),
            ("OPS-POLLING-001", OperationsMonitoringPage, "open_polling", "运维巡检只读探查"),
            ("OPERATION-KANBAN-001", OperationManagementPage, "open_operational_kanban", "运营看板只读探查"),
            ("OPERATION-INSIGHT-001", OperationManagementPage, "open_performance_insight", "效能洞察只读探查"),
            ("OPERATION-DASHBOARD-001", OperationManagementPage, "open_group_dashboard", "应用看板只读探查"),
            ("OPERATION-MESSAGE-001", OperationManagementPage, "open_message_delivery", "消息推送只读探查"),
        ],
        ids=[
            "OPS-CAPACITY-001",
            "OPS-PERFORMANCE-001",
            "OPS-POLLING-001",
            "OPERATION-KANBAN-001",
            "OPERATION-INSIGHT-001",
            "OPERATION-DASHBOARD-001",
            "OPERATION-MESSAGE-001",
        ],
    )
    def test_operations_page_shell(
        self,
        logged_in_page,
        case_id: str,
        page_class,
        method_name: str,
        action_name: str,
    ) -> None:
        """Require the real menu route, visible heading, and clean browser health."""
        health = BrowserHealthMonitor(logged_in_page, action_name).start()
        try:
            target_page = page_class(logged_in_page)
            getattr(target_page, method_name)()
        finally:
            health.stop()
        health.assert_healthy()
