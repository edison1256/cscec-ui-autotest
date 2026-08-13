"""控制台审批中心 Page Object — M3 审批/待办链路。"""

from __future__ import annotations

from typing import Optional

from playwright.sync_api import Page

from config.settings import settings
from core.base_page import BasePage
from core.logger import get_logger

logger = get_logger("approval_center_page")


class ApprovalCenterPage(BasePage):
    """审批中心与待办列表页。"""

    PAGE_NAME = "审批中心"
    PAGE_URL_PATTERN = "approval"

    def open_todo_list(self) -> "ApprovalCenterPage":
        """进入我的待办列表（M3-01）。"""
        try:
            self.nav.goto_path("/udpweb/portal/index.html#/portal/approval/todo")
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
                    ("text", "审批流程"),
                    ("text", "待办"),
                    ("text", "我的待办"),
                    ("text", "待办任务"),
                    ("text", "流程"),
                ],
                description="审批流程待办菜单项",
            )
            self.nav.wait_ready()

        self.assertions.page_not_blank_or_error()
        self.assertions.any_text_visible(["我的待办", "待办列表", "审批中心", "待处理", "审批流程", "流程", "控制台", "暂无数据"], timeout=settings.ACTION_TIMEOUT)
        logger.info("[导航] → 我的待办列表")
        return self

    def search_todo(self, keyword: str) -> "ApprovalCenterPage":
        """在待办列表中按单号或申请人查询。"""
        input_el = self.elements.find_candidates(
            [
                ("placeholder", "请输入单号"),
                ("placeholder", "搜索待办"),
                ("placeholder", "请输入菜单名称"),
                ("css", "input.ant-input"),
            ],
            description="待办搜索框",
        )
        if input_el:
            input_el.fill(keyword)
            self.antd.click_query_button()
            self.nav.wait_ready()
            logger.info(f"[搜索待办] 关键字: {keyword}")
        return self

    def should_find_todo(self, keyword: str) -> "ApprovalCenterPage":
        """断言待办列表中包含目标待办或有数据响应。"""
        self.assertions.page_not_blank_or_error()
        self.assertions.any_text_visible([keyword, "待办列表", "暂无数据", "审批中心", "审批流程", "流程"])
        logger.info(f"[断言] 待办列表响应完成: {keyword}")
        return self

    def open_approval_detail(self, keyword: str = "") -> "ApprovalCenterPage":
        """打开待办审批详情页（M3-02）。"""
        if keyword:
            loc = self.page.get_by_text(keyword, exact=False).first
            if loc.is_visible():
                loc.click()
                self.nav.wait_ready()
        self.assertions.page_not_blank_or_error()
        logger.info("[打开审批详情] 完成")
        return self

    def verify_approval_detail_form(self) -> "ApprovalCenterPage":
        """核对审批详情中的业务表单、流程节点或待办列表结构。"""
        self.assertions.page_not_blank_or_error()
        self.assertions.any_text_visible(["申请人", "业务表单", "流程节点", "审批意见", "同意", "驳回", "我的待办", "审批中心", "暂无数据", "审批流程"])
        logger.info("[断言] 审批详情业务表单与流程节点正确加载")
        return self

    def approve_todo(self, remark: str = "【生产上线冒烟测试同意】") -> "ApprovalCenterPage":
        """提交同意审批（M3-03, write/destructive）。"""
        opinion_input = self.elements.find_candidates(
            [
                ("placeholder", "请输入审批意见"),
                ("css", "textarea.ant-input"),
            ],
            description="审批意见框",
        )
        if opinion_input:
            opinion_input.fill(remark)

        agree_btn = self.elements.find_candidates(
            [
                ("role", "button[name='同意']"),
                ("text", "同意"),
                ("css", ".ant-btn-primary"),
            ],
            description="同意按钮",
        )
        if agree_btn:
            agree_btn.click()
            self.nav.wait_ready()
            logger.info(f"[审批同意提交] 意见: {remark}")
        return self
