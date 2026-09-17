"""Batch H1 candidates for resource-catalog management leaves."""

from __future__ import annotations

import pytest

from core.browser_health import BrowserHealthMonitor
from pages.console.resource_catalog_management_page import (
    ResourceCatalogManagementPage,
)


pytestmark = [
    pytest.mark.console,
    pytest.mark.readonly,
    pytest.mark.regression,
    pytest.mark.domain_split,
]


class TestResourceCatalogManagementReadonly:
    """Exercise the four H1 leaves without invoking write actions."""

    @pytest.mark.parametrize(
        ("case_id", "method_name", "action_name"),
        [
            ("RESOURCE-APP-001", "inspect_application_list_and_detail", "应用管理列表与详情只读探查"),
            ("RESOURCE-CLOUD-001", "inspect_cloud_product_list_and_detail", "云产品管理列表与详情只读探查"),
            ("RESOURCE-API-001", "inspect_api_management_shell", "API管理应用选择区只读探查"),
            ("RESOURCE-COMPONENT-001", "inspect_component_management_shell", "组件管理页面只读探查"),
        ],
        ids=[
            "RESOURCE-APP-001",
            "RESOURCE-CLOUD-001",
            "RESOURCE-API-001",
            "RESOURCE-COMPONENT-001",
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
