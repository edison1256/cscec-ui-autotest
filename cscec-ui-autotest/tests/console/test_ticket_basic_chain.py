"""M4-工单基础链路上线冒烟测试用例。

用例：
- M4-01 固定工单处理人可打开工单列表并查询
- M4-02 工单详情核心信息可见
- M4-03 低影响测试工单最小处理后状态同步 (write)
- M4-04 工单管理动作安全边界
"""

from __future__ import annotations

import pytest

from core.browser_health import BrowserHealthMonitor
from pages.console.ticket_center_page import TicketCenterPage


@pytest.mark.ticket
@pytest.mark.regression
class TestTicketBasicChain:
    """M4 工单基础链路上线冒烟用例集。"""

    @pytest.mark.smoke
    @pytest.mark.readonly
    @pytest.mark.prod_conditional
    def test_m4_01_ticket_list_search_accessible(
        self,
        logged_in_page,
        require_case_prerequisite,
    ) -> None:
        """M4-01 固定工单处理人可打开工单列表并查询。"""
        ticket_page = TicketCenterPage(logged_in_page).prepare_console_menu()
        require_case_prerequisite("M4-01", ticket_page.menu_prerequisite())
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            "M4-01",
            "工单列表查询",
        ).start()
        try:
            snapshot = ticket_page.open_ticket_management()
            require_case_prerequisite(
                "M4-01",
                ticket_page.sample_prerequisite(snapshot),
            )
            ticket_page.query_existing_ticket(snapshot)
        finally:
            health.stop()
        health.assert_healthy()

    @pytest.mark.smoke
    @pytest.mark.readonly
    @pytest.mark.prod_conditional
    def test_m4_02_ticket_detail_info_visible(
        self,
        logged_in_page,
        require_case_prerequisite,
    ) -> None:
        """M4-02 工单详情核心信息可见。"""
        ticket_page = TicketCenterPage(logged_in_page).prepare_console_menu()
        require_case_prerequisite("M4-02", ticket_page.menu_prerequisite())
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            "M4-02",
            "工单详情及处理记录",
        ).start()
        try:
            snapshot = ticket_page.open_ticket_management()
            require_case_prerequisite(
                "M4-02",
                ticket_page.sample_prerequisite(snapshot),
            )
            selected = ticket_page.query_existing_ticket(snapshot)
            ticket_page.inspect_ticket_detail(selected)
        finally:
            health.stop()
        health.assert_healthy()

    @pytest.mark.smoke
    @pytest.mark.readonly
    @pytest.mark.prod_conditional
    def test_m4_04_ticket_management_action_boundaries(
        self,
        logged_in_page,
        require_case_prerequisite,
    ) -> None:
        """M4-04 工单管理行只验证动作边界，不触发提醒或处理。"""
        ticket_page = TicketCenterPage(logged_in_page).prepare_console_menu()
        require_case_prerequisite("M4-04", ticket_page.menu_prerequisite())
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            "M4-04",
            "工单管理动作安全边界",
        ).start()
        try:
            snapshot = ticket_page.open_ticket_management()
            require_case_prerequisite(
                "M4-04",
                ticket_page.sample_prerequisite(snapshot),
            )
            selected = ticket_page.query_existing_ticket(snapshot)
            ticket_page.verify_management_action_boundaries(selected)
        finally:
            health.stop()
        health.assert_healthy()

    @pytest.mark.write
    def test_m4_03_process_ticket_minimal_status_sync(self, logged_in_page):
        """M4-03 低影响测试工单最小处理后状态同步。"""
        ticket_page = TicketCenterPage(logged_in_page)
        ticket_page.open_ticket_list()
        ticket_page.open_ticket_detail()
        ticket_page.process_ticket_minimal("【生产上线冒烟处理】完成测试工单处理")
