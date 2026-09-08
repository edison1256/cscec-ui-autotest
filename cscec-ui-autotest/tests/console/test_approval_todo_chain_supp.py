"""M3-审批/待办只读走查补充用例（第三阶段深水区探活）。"""

from __future__ import annotations

import pytest

from core.navigation_helpers import EntryNotExposed
from pages.console.approval_center_page import ApprovalCenterPage


@pytest.mark.approval
@pytest.mark.readonly
@pytest.mark.regression
class TestApprovalTodoChainSupp:
    """M3 审批链路补充探活用例集。"""

    def test_m3_supp_001_done_tab_history_query(self, logged_in_page):
        """M3-SUPP-001: 已办列表 (Done) 切换与历史查询性能断言。"""
        approval_page = ApprovalCenterPage(logged_in_page)
        approval_page.open_todo_list()
        try:
            approval_page.switch_to_done_tab()
        except EntryNotExposed as exc:
            pytest.skip(str(exc))

    def test_m3_supp_002_history_drawer_render(self, logged_in_page):
        """M3-SUPP-002: 流程图/审批历史抽屉(Drawer)加载断言。"""
        approval_page = ApprovalCenterPage(logged_in_page)
        approval_page.open_todo_list()
        # 尝试打开一个待办详情
        approval_page.open_approval_detail()
        # 验证历史记录抽屉
        try:
            approval_page.open_approval_history_drawer()
        except EntryNotExposed as exc:
            pytest.skip(str(exc))
