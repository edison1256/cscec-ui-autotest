"""Batch O approval flow management and monitoring coverage."""

from __future__ import annotations

import pytest

from core.browser_health import BrowserHealthMonitor
from pages.console.approval_flow_management_page import ApprovalFlowManagementPage


@pytest.mark.console
@pytest.mark.readonly
@pytest.mark.smoke
@pytest.mark.prod_mandatory
@pytest.mark.regression
@pytest.mark.domain_split
class TestApprovalFlowManagementReadonly:
    """Validate approval flow administration without changing process state."""

    def test_flow_management_dynamic_list(self, logged_in_page) -> None:
        """Bind the flow-management list to a dynamic production template."""
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            "FLOW-MANAGEMENT-001",
            "流程管理只读探查",
        ).start()
        try:
            ApprovalFlowManagementPage(
                logged_in_page
            ).inspect_flow_management_list()
        finally:
            health.stop()
        health.assert_healthy()

    def test_flow_monitor_first_history(self, logged_in_page) -> None:
        """Bind a process instance to its task-history panel and APIs."""
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            "FLOW-MONITOR-001",
            "流程监控历史只读探查",
        ).start()
        try:
            ApprovalFlowManagementPage(
                logged_in_page
            ).inspect_flow_monitor_history()
        finally:
            health.stop()
        health.assert_healthy()
