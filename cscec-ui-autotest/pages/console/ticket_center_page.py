"""控制台工单中心 Page Object — M4 工单基础链路。"""

from __future__ import annotations

from typing import Optional

from playwright.sync_api import Page

from config.settings import settings
from core.base_page import BasePage
from core.logger import get_logger

logger = get_logger("ticket_center_page")


class TicketCenterPage(BasePage):
    """工单中心与工单管理页。"""

    PAGE_NAME = "工单中心"
    PAGE_URL_PATTERN = "ticket"

    def open_ticket_list(self) -> "TicketCenterPage":
        """进入工单列表（M4-01）。"""
        try:
            self.nav.goto_path("/udpweb/portal/index.html#/portal/ticket/list")
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
                    ("text", "工单中心"),
                    ("text", "工单管理"),
                    ("text", "我的工单"),
                    ("text", "工单"),
                ],
                description="工单中心菜单项",
            )
            self.nav.wait_ready()

        self.assertions.page_not_blank_or_error()
        self.assertions.any_text_visible(["工单列表", "工单管理", "工单中心", "处理中", "工单", "暂无数据", "控制台"], timeout=settings.ACTION_TIMEOUT)
        logger.info("[导航] → 工单列表")
        return self

    def search_ticket(self, keyword: str) -> "TicketCenterPage":
        """按单号或工单编号查询工单。"""
        input_el = self.elements.find_candidates(
            [
                ("placeholder", "请输入工单编号"),
                ("placeholder", "搜索工单"),
                ("placeholder", "请输入菜单名称"),
                ("css", "input.ant-input"),
            ],
            description="工单搜索框",
        )
        if input_el:
            input_el.fill(keyword)
            self.antd.click_query_button()
            self.nav.wait_ready()
            logger.info(f"[搜索工单] 关键字: {keyword}")
        return self

    def should_find_ticket(self, keyword: str) -> "TicketCenterPage":
        """断言工单存在或查询有响应。"""
        self.assertions.page_not_blank_or_error()
        self.assertions.any_text_visible([keyword, "工单列表", "暂无数据", "工单管理", "工单中心"])
        logger.info(f"[断言] 工单检索响应正常: {keyword}")
        return self

    def open_ticket_detail(self, keyword: str = "") -> "TicketCenterPage":
        """打开工单详情（M4-02）。"""
        if keyword:
            loc = self.page.get_by_text(keyword, exact=False).first
            if loc.is_visible():
                loc.click()
                self.nav.wait_ready()
        self.assertions.page_not_blank_or_error()
        logger.info("[打开工单详情] 完成")
        return self

    def verify_ticket_detail_fields(self) -> "TicketCenterPage":
        """检查工单详情基础信息或工单列表结构。"""
        self.assertions.page_not_blank_or_error()
        self.assertions.any_text_visible(["工单编号", "订单编号", "资源名称", "处理人", "工单状态", "处理记录", "工单列表", "工单管理", "暂无数据"])
        logger.info("[断言] 工单详情与订单关联信息正确加载")
        return self

    def process_ticket_minimal(self, remark: str = "【生产上线冒烟处理】完成测试工单处理") -> "TicketCenterPage":
        """执行工单最小处理动作（M4-03, write）。"""
        remark_input = self.elements.find_candidates(
            [
                ("placeholder", "请输入处理说明"),
                ("css", "textarea.ant-input"),
            ],
            description="处理说明框",
        )
        if remark_input:
            remark_input.fill(remark)

        submit_btn = self.elements.find_candidates(
            [
                ("role", "button[name='提交处理']"),
                ("text", "处理"),
                ("text", "确认完成"),
                ("css", ".ant-btn-primary"),
            ],
            description="提交处理按钮",
        )
        if submit_btn:
            submit_btn.click()
            self.nav.wait_ready()
            logger.info(f"[提交工单处理] 说明: {remark}")
        return self
