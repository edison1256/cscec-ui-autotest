"""M3-审批/待办/消息上线冒烟测试用例。

用例：
- M3-01 固定审批处理人可打开待办列表
- M3-02 审批详情业务表单和流程信息可见
- M3-03 审批同意后订单状态同步更新 (write)
- M3-04 消息/小铃铛/待办跳转详情可用
"""

from __future__ import annotations

import pytest

from pages.console.approval_center_page import ApprovalCenterPage
from pages.portal.message_center_page import MessageCenterPage


@pytest.mark.approval
@pytest.mark.regression
class TestApprovalTodoChain:
    """M3 审批/待办/消息上线冒烟用例集。"""

    @pytest.mark.smoke
    @pytest.mark.readonly
    def test_m3_01_todo_list_accessible(self, logged_in_page):
        """M3-01 固定审批处理人可打开待办列表。"""
        approval_page = ApprovalCenterPage(logged_in_page)
        approval_page.open_todo_list()
        approval_page.search_todo("ORD-SMOKE")
        approval_page.should_find_todo("ORD-SMOKE")

    @pytest.mark.smoke
    @pytest.mark.readonly
    def test_m3_02_approval_detail_form_visible(self, logged_in_page):
        """M3-02 审批详情业务表单和流程信息可见。"""
        approval_page = ApprovalCenterPage(logged_in_page)
        approval_page.open_todo_list()
        approval_page.open_approval_detail()
        approval_page.verify_approval_detail_form()

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
    def test_m3_04_message_bell_click_and_navigate(self, logged_in_page):
        """M3-04 消息/小铃铛/待办跳转详情可用。"""
        msg_page = MessageCenterPage(logged_in_page)
        msg_page.open_message_bell()
        msg_page.open_message_item_and_navigate()
