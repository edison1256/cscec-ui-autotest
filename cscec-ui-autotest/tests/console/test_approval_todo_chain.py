"""M3-审批/待办/消息上线冒烟测试用例。

用例：
- M3-01 真实菜单待办查询与空态一致性
- M3-02 已办业务表单与审批流程详情只读验证
- M3-03 审批同意后订单状态同步更新 (write)
- M3-04 铃铛面板与未读消息业务跳转严格验证
"""

from __future__ import annotations

import pytest

from core.browser_health import BrowserHealthMonitor
from pages.console.approval_center_page import ApprovalCenterPage
from pages.portal.message_center_page import MessageCenterPage


@pytest.mark.approval
@pytest.mark.regression
class TestApprovalTodoChain:
    """M3 审批/待办/消息上线冒烟用例集。"""

    @pytest.mark.smoke
    @pytest.mark.readonly
    @pytest.mark.prod_conditional
    def test_m3_01_todo_list_accessible(
        self,
        logged_in_page,
        require_case_prerequisite,
    ) -> None:
        """M3-01 真实菜单待办查询与空态一致性。"""
        approval_page = ApprovalCenterPage(logged_in_page).prepare_console_menu()
        require_case_prerequisite("M3-01", approval_page.menu_prerequisite())
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            "M3-01",
            "待办流程查询",
        ).start()
        try:
            approval_page.open_approval_center()
            approval_page.query_missing_pending_flow()
        finally:
            health.stop()
        health.assert_healthy()

    @pytest.mark.smoke
    @pytest.mark.readonly
    @pytest.mark.prod_conditional
    def test_m3_02_approval_detail_form_visible(
        self,
        logged_in_page,
        require_case_prerequisite,
    ) -> None:
        """M3-02 已办业务表单与审批流程详情只读验证。"""
        approval_page = ApprovalCenterPage(logged_in_page).prepare_console_menu()
        require_case_prerequisite("M3-02", approval_page.menu_prerequisite())
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            "M3-02",
            "已办业务表单和审批流程",
        ).start()
        try:
            approval_page.open_approval_center()
            completed = approval_page.open_completed_flows()
            require_case_prerequisite(
                "M3-02",
                approval_page.completed_flow_prerequisite(completed),
            )
            approval_page.inspect_completed_business_and_flow(completed)
        finally:
            health.stop()
        health.assert_healthy()

    @pytest.mark.write
    @pytest.mark.destructive
    def test_m3_03_approve_test_order_status_sync(self, logged_in_page):
        """M3-03 审批同意后订单状态同步更新。"""
        approval_page = ApprovalCenterPage(logged_in_page)
        approval_page.open_todo_list()
        approval_page.open_approval_detail()
        approval_page.approve_todo("【生产上线冒烟测试同意】")

    @pytest.mark.smoke
    @pytest.mark.readonly
    @pytest.mark.prod_conditional
    def test_m3_04_message_bell_click_and_navigate(
        self,
        logged_in_page,
        require_case_prerequisite,
    ) -> None:
        """M3-04 铃铛面板与未读消息业务跳转严格验证。"""
        msg_page = MessageCenterPage(logged_in_page).open_console_home()
        panel_health = BrowserHealthMonitor.for_case(
            logged_in_page,
            "M3-04",
            "消息铃铛和未读接口",
        ).start()
        try:
            snapshot = msg_page.open_message_bell()
        finally:
            panel_health.stop()
        panel_health.assert_healthy()

        require_case_prerequisite(
            "M3-04",
            msg_page.navigable_message_prerequisite(snapshot),
        )
        target_health = BrowserHealthMonitor(
            logged_in_page,
            "未读消息业务落地",
        ).start()
        try:
            msg_page.open_message_target(snapshot)
        finally:
            target_health.stop()
        target_health.assert_healthy()
