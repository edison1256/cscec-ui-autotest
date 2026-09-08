"""M2-订阅/订单只读走查补充用例（第二阶段深水区探活）。"""

from __future__ import annotations

import pytest

from core.navigation_helpers import EntryNotExposed
from pages.console.order_mgmt_page import OrderMgmtPage


@pytest.mark.order
@pytest.mark.readonly
@pytest.mark.regression
class TestOrderSubscriptionChainSupp:
    """M2 订阅/订单链路补充探活用例集。"""

    def test_m2_supp_001_order_status_tab_switching(self, logged_in_page):
        """M2-SUPP-001: 订单状态 Tab 页签快速切换防抖断言。"""
        order_page = OrderMgmtPage(logged_in_page)
        order_page.open_order_list()
        try:
            order_page.switch_order_status_tabs()
        except EntryNotExposed as exc:
            pytest.skip(str(exc))

    def test_m2_supp_002_search_reset_logic(self, logged_in_page):
        """M2-SUPP-002: 重置功能 (Reset) 鲁棒性验证。"""
        order_page = OrderMgmtPage(logged_in_page)
        order_page.open_order_list()
        order_page.verify_search_reset_logic()

    def test_m2_supp_003_approval_steps_rendering(self, logged_in_page):
        """M2-SUPP-003: 订单详情审批进度条 (Steps) 渲染断言。"""
        order_page = OrderMgmtPage(logged_in_page)
        order_page.open_order_list()
        try:
            order_page.verify_approval_steps_rendered()
        except EntryNotExposed as exc:
            pytest.skip(str(exc))
