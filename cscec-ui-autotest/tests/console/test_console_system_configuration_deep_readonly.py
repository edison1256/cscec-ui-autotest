"""Batch E candidates for system-configuration resource pages."""

from __future__ import annotations

import pytest

from core.browser_health import BrowserHealthMonitor, BusinessResponseRule
from pages.console.system_configuration_page import SystemConfigurationPage


pytestmark = [
    pytest.mark.console,
    pytest.mark.readonly,
    pytest.mark.regression,
    pytest.mark.domain_split,
]


def _monitor(page, name: str, api_pattern: str | None = None) -> BrowserHealthMonitor:
    rules = (BusinessResponseRule(api_pattern),) if api_pattern else ()
    return BrowserHealthMonitor(page, name, business_rules=rules).start()


class TestConsoleSystemConfigurationDeepReadonly:
    """Enter every Batch E page through its real production menu path."""

    @pytest.mark.parametrize(
        ("method_name", "action_name", "api_pattern"),
        [
            (
                "open_category_management",
                "类目管理只读探查",
                r"/category/queryAllResourceLabel",
            ),
            (
                "open_specification_management",
                "规格管理只读探查",
                r"/category-backend/queryCategoryTreeList",
            ),
            (
                "open_data_layer_settings",
                "数据分层设置只读探查",
                r"/data-system/dataCategoryList",
            ),
            (
                "open_manufacturer_management",
                "厂商管理只读探查",
                r"/manufacturer/page",
            ),
        ],
    )
    def test_system_configuration_list_identity(
        self,
        logged_in_page,
        method_name: str,
        action_name: str,
        api_pattern: str,
    ) -> None:
        """Validate a page's critical API and dynamic visible identity."""
        health = _monitor(logged_in_page, action_name, api_pattern)
        try:
            page = SystemConfigurationPage(logged_in_page)
            getattr(page, method_name)()
        finally:
            health.stop()
        health.assert_healthy()

    def test_data_system_maintenance_real_menu_route(self, logged_in_page) -> None:
        """SYSCFG-DATASYSTEM-001: the declared menu must not bounce home."""
        health = _monitor(logged_in_page, "数据系统维护真实菜单探活")
        try:
            SystemConfigurationPage(
                logged_in_page
            ).open_data_system_maintenance()
        finally:
            health.stop()
        health.assert_healthy()
