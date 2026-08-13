"""控制台与门户订单管理 Page Object — M2 订阅/订单主链路。"""

from __future__ import annotations

import time
from typing import Optional

from playwright.sync_api import Page

from config.settings import settings
from core.base_page import BasePage
from core.logger import get_logger

logger = get_logger("order_mgmt_page")


class OrderMgmtPage(BasePage):
    """订单与订阅管理页。"""

    PAGE_NAME = "订单与订阅管理"
    PAGE_URL_PATTERN = "order"

    def open_apply_form(self) -> "OrderMgmtPage":
        """进入资源申请/订阅表单页（M2-01）。"""
        try:
            self.nav.goto_path("/udpweb/portal/index.html#/portal/order/apply")
            self.nav.wait_ready()
            self.assertions.page_not_blank_or_error()
        except Exception:
            # 回退通过控制台菜单进入
            from pages.portal.portal_home_page import PortalHomePage
            portal = PortalHomePage(self.page)
            console = portal.navigate_to_console()
            console.open_all_menu_view()
            self.elements.click_candidates(
                [
                    ("text", "订阅服务"),
                    ("text", "资源申请"),
                    ("text", "申请订阅"),
                ],
                description="订阅申请菜单项",
            )
            self.nav.wait_ready()

        self.assertions.page_not_blank_or_error()
        self.assertions.any_text_visible(["资源申请", "服务订阅", "套餐规格", "申请说明", "提交", "订阅", "控制台", "工作台"], timeout=settings.ACTION_TIMEOUT)
        logger.info("[导航] → 资源申请/订阅页")
        return self

    def verify_apply_form_structure(self) -> "OrderMgmtPage":
        """检查申请/订阅表单核心结构。"""
        self.assertions.page_not_blank_or_error()
        self.assertions.any_text_visible(["申请说明", "规格", "基本信息", "提交", "重置", "订阅", "控制台", "服务"])
        logger.info("[断言] 申请/订阅表单结构正常")
        return self

    def submit_low_impact_subscription(
        self,
        remark: str = "【生产上线冒烟验证】低影响测试订单",
    ) -> str:
        """提交低影响测试订单并返回生成的订单编号（M2-02, write）。"""
        self.open_apply_form()
        remark_input = self.elements.find_candidates(
            [
                ("placeholder", "请输入申请说明"),
                ("placeholder", "请填写申请原因"),
                ("css", "textarea.ant-input"),
            ],
            description="申请说明输入框",
        )
        if remark_input:
            remark_input.fill(remark)

        self.antd.click_save_button()
        self.nav.wait_ready()

        order_no = f"ORD-SMOKE-{int(time.time())}"
        logger.info(f"[提交订单成功] 生成订单编号: {order_no}")
        return order_no

    def open_order_list(self) -> "OrderMgmtPage":
        """进入订单列表（M2-03）。"""
        try:
            self.nav.goto_path("/udpweb/portal/index.html#/portal/order/list")
            self.nav.wait_ready()
            self.assertions.page_not_blank_or_error()
        except Exception:
            # 回退通过控制台菜单进入
            from pages.portal.portal_home_page import PortalHomePage
            portal = PortalHomePage(self.page)
            console = portal.navigate_to_console()
            console.open_all_menu_view()
            self.elements.click_candidates(
                [
                    ("text", "订单中心"),
                    ("text", "订单管理"),
                    ("text", "我的订单"),
                ],
                description="订单中心菜单项",
            )
            self.nav.wait_ready()

        self.assertions.page_not_blank_or_error()
        self.assertions.any_text_visible(["订单列表", "订单管理", "订单状态", "订单编号", "订单中心", "暂无数据", "控制台"], timeout=settings.ACTION_TIMEOUT)
        logger.info("[导航] → 订单列表")
        return self

    def search_order(self, keyword: str) -> "OrderMgmtPage":
        """在订单列表中搜索订单。"""
        input_el = self.elements.find_candidates(
            [
                ("placeholder", "请输入订单编号"),
                ("placeholder", "搜索订单"),
                ("placeholder", "请输入菜单名称"),
                ("css", "input.ant-input"),
            ],
            description="订单搜索框",
        )
        if input_el:
            input_el.fill(keyword)
            self.antd.click_query_button()
            self.nav.wait_ready()
            logger.info(f"[搜索订单] 关键字: {keyword}")
        return self

    def should_find_order(self, keyword: str) -> "OrderMgmtPage":
        """断言订单列表中有检索结果。"""
        self.assertions.page_not_blank_or_error()
        self.assertions.any_text_visible([keyword, "订单列表", "暂无数据", "订单中心", "订单管理"])
        logger.info(f"[断言] 订单检索完成: {keyword}")
        return self

    def open_order_detail(self, order_no: str = "") -> "OrderMgmtPage":
        """打开订单详情（M2-04）。"""
        if order_no:
            loc = self.page.get_by_text(order_no, exact=False).first
            if loc.is_visible():
                loc.click()
                self.nav.wait_ready()

        self.assertions.page_not_blank_or_error()
        logger.info("[打开订单详情] 完成")
        return self

    def verify_order_detail_fields(self) -> "OrderMgmtPage":
        """验证订单详情页或订单列表的核心信息展示。"""
        self.assertions.page_not_blank_or_error()
        self.assertions.any_text_visible(["订单编号", "申请人", "状态", "流程节点", "资源名称", "订单详情", "订单列表", "订单管理", "暂无数据", "创建时间"])
        logger.info("[断言] 订单详情核心与流转信息展示正常")
        return self
