"""Batch D candidates for secondary console pages."""

from __future__ import annotations

import pytest

from core.browser_health import BrowserHealthMonitor
from pages.console.evaluation_management_page import EvaluationManagementPage
from pages.console.metering_statistics_page import MeteringStatisticsPage
from pages.console.system_configuration_page import SystemConfigurationPage


pytestmark = [
    pytest.mark.console,
    pytest.mark.readonly,
    pytest.mark.regression,
    pytest.mark.domain_split,
    pytest.mark.prod_conditional,
]


def _monitor(page, case_id: str, action_name: str) -> BrowserHealthMonitor:
    """Build a monitor from the reviewed production contract."""
    return BrowserHealthMonitor.for_case(page, case_id, action_name).start()


@pytest.mark.prod_conditional
class TestConsoleSecondaryPagesDeepReadonly:
    """Validate less-travelled console lists without invoking write actions."""

    def test_evaluation_template_list(self, logged_in_page) -> None:
        """EVAL-001: validate evaluation template API and rendered identity."""
        health = _monitor(logged_in_page, "EVAL-001", "评价数据管理只读探查")
        try:
            EvaluationManagementPage(logged_in_page).open()
        finally:
            health.stop()
        health.assert_healthy()

    def test_portal_homepage_configuration(self, logged_in_page) -> None:
        """SYSCFG-PORTAL-001: validate homepage banner list identity."""
        health = _monitor(logged_in_page, "SYSCFG-PORTAL-001", "首页配置只读探查")
        try:
            SystemConfigurationPage(logged_in_page).open_homepage_configuration()
        finally:
            health.stop()
        health.assert_healthy()

    def test_audit_log_list(self, logged_in_page) -> None:
        """SYSCFG-AUDIT-001: validate audit list API and rendered identity."""
        health = _monitor(logged_in_page, "SYSCFG-AUDIT-001", "日志审计查询只读探查")
        try:
            SystemConfigurationPage(logged_in_page).open_audit_log()
        finally:
            health.stop()
        health.assert_healthy()

    def test_tenant_resource_overview(self, logged_in_page) -> None:
        """METER-RESOURCE-001: validate tenant resource overview identity."""
        health = _monitor(logged_in_page, "METER-RESOURCE-001", "租户资源概览只读探查")
        try:
            MeteringStatisticsPage(logged_in_page).open_resource_overview()
        finally:
            health.stop()
        health.assert_healthy()

    def test_tenant_subscription_overview(self, logged_in_page) -> None:
        """METER-SUBSCRIPTION-001: validate tenant subscription overview identity."""
        health = _monitor(
            logged_in_page,
            "METER-SUBSCRIPTION-001",
            "租户订阅概览只读探查",
        )
        try:
            MeteringStatisticsPage(logged_in_page).open_subscription_overview()
        finally:
            health.stop()
        health.assert_healthy()
