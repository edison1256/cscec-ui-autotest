"""M2-订阅/订单主链路上线冒烟测试用例。

用例：
- M2-01 从固定冒烟资源进入申请/订阅页
- M2-02 提交固定冒烟资源并生成低影响测试订单 (write)
- M2-03 订单列表可查询到低影响测试订单
- M2-04 测试订单详情核心信息和流转信息可见
"""

from __future__ import annotations

import pytest

from core.browser_health import BrowserHealthMonitor
from pages.console.console_workbench_page import ConsoleWorkbenchPage
from pages.console.order_mgmt_page import OrderMgmtPage


@pytest.mark.order
@pytest.mark.regression
class TestOrderSubscriptionChain:
    """M2 订阅/订单主链路冒烟用例集。"""

    @pytest.mark.smoke
    @pytest.mark.readonly
    def test_m2_01_navigate_to_apply_page(self, logged_in_page):
        """M2-01 从固定冒烟资源进入申请/订阅页。"""
        order_page = OrderMgmtPage(logged_in_page)
        order_page.open_apply_form()
        order_page.verify_apply_form_structure()

    @pytest.mark.write
    def test_m2_02_submit_low_impact_test_order(self, logged_in_page):
        """M2-02 提交固定冒烟资源并生成低影响测试订单。"""
        order_page = OrderMgmtPage(logged_in_page)
        order_no = order_page.submit_low_impact_subscription()
        assert order_no.startswith("ORD-SMOKE-")

    @pytest.mark.smoke
    @pytest.mark.readonly
    @pytest.mark.prod_conditional
    def test_m2_03_order_list_search(
        self,
        logged_in_page,
        require_case_prerequisite,
    ) -> None:
        """M2-03 订单列表可查询到低影响测试订单。"""
        order_page = OrderMgmtPage(logged_in_page).prepare_console_menu()
        require_case_prerequisite("M2-03", order_page.menu_prerequisite())
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            "M2-03",
            "订单列表查询",
        ).start()
        try:
            snapshot = order_page.open_console_orders()
            require_case_prerequisite(
                "M2-03",
                ConsoleWorkbenchPage.detail_prerequisite(snapshot),
            )
            order_page.query_existing_order(snapshot)
        finally:
            health.stop()
        health.assert_healthy()

    @pytest.mark.smoke
    @pytest.mark.readonly
    @pytest.mark.prod_conditional
    def test_m2_04_order_detail_info_visible(
        self,
        logged_in_page,
        require_case_prerequisite,
    ) -> None:
        """M2-04 测试订单详情核心信息和流转信息可见。"""
        order_page = OrderMgmtPage(logged_in_page).prepare_console_menu()
        require_case_prerequisite("M2-04", order_page.menu_prerequisite())
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            "M2-04",
            "订单详情及流转",
        ).start()
        try:
            snapshot = order_page.open_console_orders()
            require_case_prerequisite(
                "M2-04",
                ConsoleWorkbenchPage.detail_prerequisite(snapshot),
            )
            selected = order_page.query_existing_order(snapshot)
            order_page.inspect_order_detail(selected)
        finally:
            health.stop()
        health.assert_healthy()
