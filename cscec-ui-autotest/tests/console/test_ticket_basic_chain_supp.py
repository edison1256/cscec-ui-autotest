"""M4-工单基础链路只读走查补充用例（第三阶段深水区探活）。"""

from __future__ import annotations

import pytest

from core.navigation_helpers import EntryNotExposed
from pages.console.ticket_center_page import TicketCenterPage


@pytest.mark.ticket
@pytest.mark.readonly
@pytest.mark.regression
class TestTicketBasicChainSupp:
    """M4 工单基础链路补充探活用例集。"""

    def test_m4_supp_001_taxonomy_dropdown(self, logged_in_page):
        """M4-SUPP-001: 工单分类数据字典 (Taxonomy) 探活。"""
        ticket_page = TicketCenterPage(logged_in_page)
        ticket_page.open_ticket_list()
        try:
            ticket_page.verify_ticket_type_dropdown()
        except EntryNotExposed as exc:
            pytest.skip(str(exc))

    def test_m4_supp_002_modal_backdrop_clear(self, logged_in_page):
        """M4-SUPP-002: 前端弹窗遮罩层 (Modal/Backdrop) 清除测试。"""
        ticket_page = TicketCenterPage(logged_in_page)
        ticket_page.open_ticket_list()
        # 尝试打开一个工单详情
        ticket_page.open_ticket_detail()
        # 触发操作弹窗并校验遮罩销毁逻辑
        try:
            ticket_page.verify_ticket_modal_backdrop_clear()
        except EntryNotExposed as exc:
            pytest.skip(str(exc))
