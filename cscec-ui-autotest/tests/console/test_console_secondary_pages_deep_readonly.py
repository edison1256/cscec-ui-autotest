"""Batch D candidates for secondary console pages."""

from __future__ import annotations

import pytest

from core.browser_health import BrowserHealthMonitor, BusinessResponseRule
from pages.console.evaluation_management_page import EvaluationManagementPage
from pages.console.metering_statistics_page import MeteringStatisticsPage
from pages.console.system_configuration_page import SystemConfigurationPage


pytestmark = [
    pytest.mark.console,
    pytest.mark.readonly,
    pytest.mark.regression,
    pytest.mark.domain_split,
]


def _monitor(page, action_name: str, api_pattern: str) -> BrowserHealthMonitor:
    """Build a strict candidate monitor before a machine contract exists."""
    return BrowserHealthMonitor(
        page,
        action_name,
        business_rules=(BusinessResponseRule(api_pattern),),
    ).start()


class TestConsoleSecondaryPagesDeepReadonly:
    """Validate less-travelled console lists without invoking write actions."""

    def test_evaluation_template_list(self, logged_in_page) -> None:
        """EVAL-001: validate evaluation template API and rendered identity."""
        health = _monitor(logged_in_page, "评价数据管理只读探查", r"/assessment-template/page")
        try:
            EvaluationManagementPage(logged_in_page).open()
        finally:
            health.stop()
        health.assert_healthy()

    def test_portal_homepage_configuration(self, logged_in_page) -> None:
        """SYSCFG-PORTAL-001: validate homepage banner list identity."""
        health = _monitor(logged_in_page, "首页配置只读探查", r"/banner/queryIrpBannerList")
        try:
            SystemConfigurationPage(logged_in_page).open_homepage_configuration()
        finally:
            health.stop()
        health.assert_healthy()

    def test_audit_log_list(self, logged_in_page) -> None:
        """SYSCFG-AUDIT-001: validate audit list API and rendered identity."""
        health = _monitor(logged_in_page, "日志审计查询只读探查", r"/log-audit/page")
        try:
            SystemConfigurationPage(logged_in_page).open_audit_log()
        finally:
            health.stop()
        health.assert_healthy()

    def test_tenant_resource_overview(self, logged_in_page) -> None:
        """METER-RESOURCE-001: validate tenant resource overview identity."""
        health = _monitor(
            logged_in_page,
            "租户资源概览只读探查",
            r"/metrology/resource/overview/page",
        )
        try:
            MeteringStatisticsPage(logged_in_page).open_resource_overview()
        finally:
            health.stop()
        health.assert_healthy()

    def test_tenant_subscription_overview(self, logged_in_page) -> None:
        """METER-SUBSCRIPTION-001: validate tenant subscription overview identity."""
        health = _monitor(
            logged_in_page,
            "租户订阅概览只读探查",
            r"/metrology/tenant/apply/list",
        )
        try:
            MeteringStatisticsPage(logged_in_page).open_subscription_overview()
        finally:
            health.stop()
        health.assert_healthy()
