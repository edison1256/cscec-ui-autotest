"""Batch L deep read-only metering-statistics coverage."""

from __future__ import annotations

import pytest

from core.browser_health import BrowserHealthMonitor
from pages.console.metering_statistics_page import MeteringStatisticsPage


@pytest.mark.console
@pytest.mark.readonly
@pytest.mark.smoke
@pytest.mark.prod_mandatory
@pytest.mark.regression
@pytest.mark.domain_split
class TestMeteringStatisticsDeepReadonly:
    """Bind overview tenant rows to their read-only detail pages."""

    def test_first_resource_tenant_detail(self, logged_in_page) -> None:
        """Open the first resource tenant and verify its detail structure."""
        health = BrowserHealthMonitor(
            logged_in_page,
            "租户资源首条详情",
        ).start()
        try:
            MeteringStatisticsPage(
                logged_in_page
            ).inspect_first_resource_tenant_detail()
        finally:
            health.stop()
        health.assert_healthy()

    def test_first_subscription_tenant_detail(self, logged_in_page) -> None:
        """Open the first subscription tenant and verify its detail structure."""
        health = BrowserHealthMonitor(
            logged_in_page,
            "租户订阅首条详情",
        ).start()
        try:
            MeteringStatisticsPage(
                logged_in_page
            ).inspect_first_subscription_tenant_detail()
        finally:
            health.stop()
        health.assert_healthy()
