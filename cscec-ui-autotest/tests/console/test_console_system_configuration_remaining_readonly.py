"""Batch F candidates for the remaining system-configuration pages."""

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


@pytest.mark.prod_conditional
class TestConsoleSystemConfigurationRemainingReadonly:
    """Validate the remaining system-configuration pages."""

    @pytest.mark.parametrize(
        ("case_id", "method_name", "action_name"),
        [
            (
                "SYSCFG-DEVELOPER-001",
                "open_developer_platform_configuration",
                "开发者平台配置只读探查",
            ),
            (
                "SYSCFG-INSPECTION-001",
                "open_inspection_configuration",
                "巡检配置只读探查",
            ),
            (
                "SYSCFG-WORKORDER-001",
                "open_work_order_configuration",
                "工单配置只读探查",
            ),
        ],
        ids=[
            "SYSCFG-DEVELOPER-001",
            "SYSCFG-INSPECTION-001",
            "SYSCFG-WORKORDER-001",
        ],
    )
    def test_remaining_system_configuration_page(
        self,
        logged_in_page,
        case_id: str,
        method_name: str,
        action_name: str,
    ) -> None:
        """Validate a real menu path, critical API, identity, and safe controls."""
        health = BrowserHealthMonitor.for_case(
            logged_in_page, case_id, action_name
        ).start()
        try:
            page = SystemConfigurationPage(logged_in_page)
            getattr(page, method_name)()
        finally:
            health.stop()
        health.assert_healthy()
