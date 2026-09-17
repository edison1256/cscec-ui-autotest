"""M1-资源基线上线冒烟测试用例。

用例：
- M1-01 代表资源列表查询可用
- M1-02 固定冒烟资源详情可打开
- M1-03 固定冒烟资源编辑页只读检查
- M1-04 门户/服务中心可搜索并打开固定冒烟资源
"""

from __future__ import annotations

import pytest

from core.browser_health import BrowserHealthMonitor
from pages.console.resource_mgmt_page import ResourceMgmtPage


@pytest.mark.resource
@pytest.mark.smoke
@pytest.mark.readonly
@pytest.mark.regression
class TestResourceBaseline:
    """M1 资源基线上线冒烟用例集。"""

    @pytest.mark.prod_conditional
    def test_m1_01_resource_list_search_available(
        self,
        logged_in_page,
        require_case_prerequisite,
    ) -> None:
        """M1-01 query the data-resource list through its real console menu."""
        resource_page = ResourceMgmtPage(logged_in_page).prepare_console_menu()
        require_case_prerequisite("M1-01", resource_page.menu_prerequisite())
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            "M1-01",
            "数据资源列表查询",
        ).start()
        try:
            resource_page.open_resource_list()
        finally:
            health.stop()
        health.assert_healthy()

    @pytest.mark.prod_conditional
    def test_m1_02_resource_detail_accessible(
        self,
        logged_in_page,
        require_case_prerequisite,
    ) -> None:
        """M1-02 open the dedicated data-resource detail from its exact row."""
        resource_page = ResourceMgmtPage(logged_in_page).prepare_console_menu()
        require_case_prerequisite("M1-02", resource_page.menu_prerequisite())
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            "M1-02",
            "数据资源专用表详情",
        ).start()
        try:
            resource_page.open_resource_list()
            resource_page.open_resource_detail(resource_page.target_record())
        finally:
            health.stop()
        health.assert_healthy()

    @pytest.mark.prod_conditional
    def test_m1_03_resource_edit_readonly_check(
        self,
        logged_in_page,
        require_case_prerequisite,
    ) -> None:
        """M1-03 inspect all edit tabs and return without submitting."""
        resource_page = ResourceMgmtPage(logged_in_page).prepare_console_menu()
        require_case_prerequisite("M1-03", resource_page.menu_prerequisite())
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            "M1-03",
            "数据资源编辑弹窗只读探查",
        ).start()
        try:
            resource_page.open_resource_list()
            resource_page.open_resource_edit_readonly(resource_page.target_record())
        finally:
            health.stop()
        health.assert_healthy()

    @pytest.mark.prod_conditional
    def test_m1_04_portal_search_and_open_resource(self, logged_in_page) -> None:
        """M1-04 门户/服务中心可搜索并打开固定冒烟资源。"""
        resource_page = ResourceMgmtPage(
            logged_in_page
        ).open_authenticated_portal_service_center()
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            "M1-04",
            "cloud 服务中心云产品搜索及详情",
        ).start()
        try:
            resource_page.search_and_open_portal_service_center("CKafka消息队列")
        finally:
            health.stop()
        health.assert_healthy()
