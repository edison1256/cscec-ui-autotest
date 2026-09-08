"""M1-资源基线只读走查补充用例（第二阶段深水区探活）。"""

from __future__ import annotations

import pytest

from pages.console.resource_mgmt_page import ResourceMgmtPage


@pytest.mark.resource
@pytest.mark.readonly
@pytest.mark.regression
class TestResourceBaselineSupp:
    """M1 资源基线补充探活用例集。"""

    def test_m1_supp_001_advanced_search(self, logged_in_page):
        """M1-SUPP-001: 资源列表多维度高级组合检索。"""
        resource_page = ResourceMgmtPage(logged_in_page)
        resource_page.open_resource_list()
        # 尝试使用“运行中”状态和关键字进行组合查询
        resource_page.search_resource_advanced(status="运行中", keyword="自动化验证")

    def test_m1_supp_002_pagination_health(self, logged_in_page):
        """M1-SUPP-002: 表格分页器抗跌与刷新验证。"""
        resource_page = ResourceMgmtPage(logged_in_page)
        resource_page.open_resource_list()
        resource_page.verify_pagination_and_table_health()

    def test_m1_supp_003_global_action_buttons(self, logged_in_page):
        """M1-SUPP-003: 全局批量操作组可用性断言。"""
        resource_page = ResourceMgmtPage(logged_in_page)
        resource_page.open_resource_list()
        resource_page.verify_global_action_buttons()
