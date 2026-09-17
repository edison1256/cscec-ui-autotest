"""Batch F candidates for the remaining system-configuration pages."""

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


@pytest.mark.parametrize(
    ("method_name", "action_name", "api_pattern"),
    [
        (
            "open_developer_platform_configuration",
            "开发者平台配置只读探查",
            r"/developer-platform-resource-portal/page",
        ),
        (
            "open_inspection_configuration",
            "巡检配置只读探查",
            r"/irpTaskTpl/getIrpTaskTplList",
        ),
        (
            "open_work_order_configuration",
            "工单配置只读探查",
            r"/work-order-config/getCategory",
        ),
    ],
)
def test_remaining_system_configuration_page(
    logged_in_page,
    method_name: str,
    action_name: str,
    api_pattern: str,
) -> None:
    """Validate a real menu path, critical API, identity, and safe controls."""
    health = BrowserHealthMonitor(
        logged_in_page,
        action_name,
        business_rules=(BusinessResponseRule(api_pattern),),
    ).start()
    try:
        page = SystemConfigurationPage(logged_in_page)
        getattr(page, method_name)()
    finally:
        health.stop()
    health.assert_healthy()
