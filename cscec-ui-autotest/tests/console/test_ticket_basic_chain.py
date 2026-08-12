"""M4-工单基础链路上线冒烟测试用例。

用例：
- M4-01 固定工单处理人可打开工单列表并查询
- M4-02 工单详情核心信息可见
- M4-03 低影响测试工单最小处理后状态同步 (write)
"""

from __future__ import annotations

import pytest

from pages.console.ticket_center_page import TicketCenterPage


@pytest.mark.ticket
@pytest.mark.regression
class TestTicketBasicChain:
    """M4 工单基础链路上线冒烟用例集。"""

    @pytest.mark.smoke
    @pytest.mark.readonly
    def test_m4_01_ticket_list_search_accessible(self, logged_in_page):
        """M4-01 固定工单处理人可打开工单列表并查询。"""
        ticket_page = TicketCenterPage(logged_in_page)
        ticket_page.open_ticket_list()
        ticket_page.search_ticket("TCK-SMOKE")
        ticket_page.should_find_ticket("TCK-SMOKE")

    @pytest.mark.smoke
    @pytest.mark.readonly
    def test_m4_02_ticket_detail_info_visible(self, logged_in_page):
        """M4-02 工单详情核心信息可见。"""
        ticket_page = TicketCenterPage(logged_in_page)
        ticket_page.open_ticket_list()
        ticket_page.open_ticket_detail()
        ticket_page.verify_ticket_detail_fields()

    @pytest.mark.write
    def test_m4_03_process_ticket_minimal_status_sync(self, logged_in_page):
        """M4-03 低影响测试工单最小处理后状态同步。"""
        ticket_page = TicketCenterPage(logged_in_page)
        ticket_page.open_ticket_list()
        ticket_page.open_ticket_detail()
        ticket_page.process_ticket_minimal("【生产上线冒烟处理】完成测试工单处理")
