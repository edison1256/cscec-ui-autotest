"""Batch H1 candidates for resource-catalog management leaves."""

from __future__ import annotations

import pytest

from config.settings import settings
from core.browser_health import BrowserHealthMonitor
from pages.console.resource_catalog_management_page import (
    ResourceCatalogManagementPage,
)


pytestmark = [
    pytest.mark.console,
    pytest.mark.readonly,
    pytest.mark.smoke,
    pytest.mark.prod_mandatory,
    pytest.mark.regression,
    pytest.mark.domain_split,
]


@pytest.mark.smoke
@pytest.mark.prod_mandatory
class TestResourceCatalogManagementReadonly:
    """Exercise the four H1 leaves without invoking write actions."""

    @pytest.mark.parametrize(
        ("case_id", "method_name", "action_name"),
        [
            ("RESOURCE-APP-001", "inspect_application_list_and_detail", "应用管理列表与详情只读探查"),
            ("RESOURCE-CLOUD-001", "inspect_cloud_product_list_and_detail", "云产品管理列表与详情只读探查"),
            ("RESOURCE-API-001", "inspect_api_management_shell", "API管理应用选择区只读探查"),
            ("RESOURCE-COMPONENT-001", "inspect_component_management_shell", "组件管理页面只读探查"),
            ("RESOURCE-DATA-ASSET-001", "inspect_data_asset_list_and_detail", "数据资产管理列表与详情只读探查"),
            ("RESOURCE-SOLUTION-001", "inspect_solution_list_and_detail", "解决方案管理列表与详情只读探查"),
            ("RESOURCE-HARDWARE-001", "inspect_hardware_management_shell", "硬件管理页面只读探查"),
        ],
        ids=[
            "RESOURCE-APP-001",
            "RESOURCE-CLOUD-001",
            "RESOURCE-API-001",
            "RESOURCE-COMPONENT-001",
            "RESOURCE-DATA-ASSET-001",
            "RESOURCE-SOLUTION-001",
            "RESOURCE-HARDWARE-001",
        ],
    )
    def test_resource_catalog_leaf(
        self,
        logged_in_page,
        case_id: str,
        method_name: str,
        action_name: str,
    ) -> None:
        """Require a real menu path, strict page evidence, and browser health."""
        health = BrowserHealthMonitor(logged_in_page, action_name).start()
        try:
            catalog = ResourceCatalogManagementPage(logged_in_page)
            getattr(catalog, method_name)()
        finally:
            health.stop()
        health.assert_healthy()

    @pytest.mark.skipif(settings.ENV != "prod", reason="仅使用生产专用测试样本")
    @pytest.mark.parametrize(
        ("case_id", "method_name", "action_name"),
        [
            (
                "RESOURCE-APP-CONFIRM-001",
                "inspect_prod_application_unpublish_confirmation",
                "生产专用应用下架确认框只读探查",
            ),
            (
                "RESOURCE-CLOUD-CONFIRM-001",
                "inspect_prod_cloud_delete_confirmation",
                "生产专用云产品删除确认框只读探查",
            ),
        ],
        ids=["RESOURCE-APP-CONFIRM-001", "RESOURCE-CLOUD-CONFIRM-001"],
    )
    def test_prod_dedicated_sample_confirmation_guard(
        self,
        logged_in_page,
        case_id: str,
        method_name: str,
        action_name: str,
    ) -> None:
        """Reach a destructive confirmation boundary and cancel without writes."""
        health = BrowserHealthMonitor(logged_in_page, action_name).start()
        try:
            catalog = ResourceCatalogManagementPage(logged_in_page)
            getattr(catalog, method_name)()
        finally:
            health.stop()
        health.assert_healthy()
