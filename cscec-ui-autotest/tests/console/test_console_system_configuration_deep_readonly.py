"""Batch E candidates for system-configuration resource pages."""

from __future__ import annotations

import pytest

from core.browser_health import BrowserHealthMonitor
from pages.console.system_configuration_page import SystemConfigurationPage


pytestmark = [
    pytest.mark.console,
    pytest.mark.readonly,
    pytest.mark.regression,
    pytest.mark.domain_split,
    pytest.mark.prod_conditional,
]


def _monitor(page, case_id: str, name: str) -> BrowserHealthMonitor:
    return BrowserHealthMonitor.for_case(page, case_id, name).start()


@pytest.mark.prod_conditional
class TestConsoleSystemConfigurationDeepReadonly:
    """Enter every Batch E page through its real production menu path."""

    @pytest.mark.parametrize(
        ("case_id", "method_name", "action_name"),
        [
            (
                "SYSCFG-CATEGORY-001",
                "open_category_management",
                "类目管理只读探查",
            ),
            (
                "SYSCFG-SPEC-001",
                "open_specification_management",
                "规格管理只读探查",
            ),
            (
                "SYSCFG-LAYER-001",
                "open_data_layer_settings",
                "数据分层设置只读探查",
            ),
            (
                "SYSCFG-MANUFACTURER-001",
                "open_manufacturer_management",
                "厂商管理只读探查",
            ),
        ],
        ids=[
            "SYSCFG-CATEGORY-001",
            "SYSCFG-SPEC-001",
            "SYSCFG-LAYER-001",
            "SYSCFG-MANUFACTURER-001",
        ],
    )
    def test_system_configuration_list_identity(
        self,
        logged_in_page,
        case_id: str,
        method_name: str,
        action_name: str,
    ) -> None:
        """Validate a page's critical API and dynamic visible identity."""
        health = _monitor(logged_in_page, case_id, action_name)
        try:
            page = SystemConfigurationPage(logged_in_page)
            getattr(page, method_name)()
        finally:
            health.stop()
        health.assert_healthy()

    def test_data_system_maintenance_real_menu_route(self, logged_in_page) -> None:
        """SYSCFG-DATASYSTEM-001: the declared menu must not bounce home."""
        health = _monitor(
            logged_in_page,
            "SYSCFG-DATASYSTEM-001",
            "数据系统维护真实菜单探活",
        )
        try:
            SystemConfigurationPage(
                logged_in_page
            ).open_data_system_maintenance()
        finally:
            health.stop()
        health.assert_healthy()
