"""M1-资源基线上线冒烟测试用例。

用例：
- M1-01 代表资源列表查询可用
- M1-02 固定冒烟资源详情可打开
- M1-03 固定冒烟资源编辑页只读检查
- M1-04 门户/服务中心可搜索并打开固定冒烟资源
"""

from __future__ import annotations

import pytest

from pages.console.resource_mgmt_page import ResourceMgmtPage


@pytest.mark.resource
@pytest.mark.smoke
@pytest.mark.readonly
@pytest.mark.regression
class TestResourceBaseline:
    """M1 资源基线上线冒烟用例集。"""

    def test_m1_01_resource_list_search_available(self, logged_in_page):
        """M1-01 控制台代表资源列表查询可用。"""
        resource_page = ResourceMgmtPage(logged_in_page)
        resource_page.open_resource_list()
        resource_page.search_resource("测试资源")
        resource_page.should_find_resource("测试资源")

    def test_m1_02_resource_detail_accessible(self, logged_in_page):
        """M1-02 控制台固定冒烟资源详情可打开。"""
        resource_page = ResourceMgmtPage(logged_in_page)
        resource_page.open_resource_list()
        resource_page.search_resource("测试资源")
        resource_page.open_resource_detail("测试资源")
        resource_page.verify_detail_fields()

    def test_m1_03_resource_edit_readonly_check(self, logged_in_page):
        """M1-03 控制台固定冒烟资源编辑页只读检查。"""
        resource_page = ResourceMgmtPage(logged_in_page)
        resource_page.open_resource_list()
        resource_page.search_resource("测试资源")
        resource_page.open_resource_edit_readonly("测试资源")
        resource_page.verify_edit_page_readonly()

    def test_m1_04_portal_search_and_open_resource(self, logged_in_page):
        """M1-04 门户/服务中心可搜索并打开固定冒烟资源。"""
        resource_page = ResourceMgmtPage(logged_in_page)
        resource_page.search_and_open_portal_service_center("测试资源")
