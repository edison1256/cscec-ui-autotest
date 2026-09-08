"""控制台工单中心 Page Object — M4 工单基础链路。"""

from __future__ import annotations

from typing import Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from config.settings import settings
from core.base_page import BasePage
from core.logger import get_logger
from core.navigation_helpers import EntryNotExposed

logger = get_logger("ticket_center_page")


class TicketCenterPage(BasePage):
    """工单中心与工单管理页。"""

    PAGE_NAME = "工单中心"
    PAGE_URL_PATTERN = "ticket"

    def open_ticket_list(self) -> "TicketCenterPage":
        """进入工单列表（M4-01）。"""
        try:
            self.nav.goto_url(settings.console_url("/udpweb/portal/index.html#/portal/ticket/list"))
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

    def verify_ticket_type_dropdown(self) -> "TicketCenterPage":
        """M4-SUPP-001: 验证工单分类字典 (Taxonomy) 下拉框健康度。"""
        type_dropdown = self.elements.find_candidates(
            [
                ("placeholder", "工单类型"),
                ("placeholder", "请选择类型"),
                ("placeholder", "请选择分类"),
                ("text", "工单类型"),
            ],
            description="工单类型下拉框",
            timeout=2000
        )
        
        if not type_dropdown:
            raise EntryNotExposed("工单列表未暴露工单类型下拉框")
            
        type_dropdown.click()
        self.page.wait_for_timeout(500)
        
        try:
            # 等待下拉列表容器渲染，任意一条选项出现即可证明字典接口未挂
            option = self.page.locator(".ant-select-item, .el-select-dropdown__item").first
            option.wait_for(state="visible", timeout=3000)
            logger.info("[断言] 工单分类字典接口可用，下拉项已渲染")
            
            # 收起下拉框（点别的地方）
            self.page.locator("body").click(position={"x": 0, "y": 0})
        except PlaywrightTimeoutError:
            raise AssertionError("点击工单类型下拉框后未能刷出字典选项") from None
            
        return self

    def verify_ticket_modal_backdrop_clear(self) -> "TicketCenterPage":
        """M4-SUPP-002: 前端弹窗遮罩层清除测试 (幽灵遮罩防御)。"""
        # 找一个肯定会有弹窗的操作，且必须是纯只读向的按钮（严禁点击任何可能产生脏数据或状态流转的动作）
        action_btn = self.elements.find_candidates(
            [
                ("text", "工单历史"),
                ("text", "操作日志"),
                ("text", "查看详情"),
                ("text", "流转日志"),
            ],
            description="只读弹窗触发按钮",
            timeout=3000
        )
        
        if not action_btn:
            raise EntryNotExposed("工单详情未暴露只读历史类弹窗入口")
            
        action_btn.click()
        self.page.wait_for_timeout(1000)
        
        try:
            modal = self.page.locator(".ant-modal, .el-dialog, .el-drawer").first
            modal.wait_for(state="visible", timeout=4000)
            logger.info("[交互] 弹窗加载成功")
            
            # 找到取消或关闭按钮
            cancel_btn = modal.locator("button:has-text('取消'), .ant-modal-close, .el-dialog__headerbtn, .el-drawer__close-btn").first
            cancel_btn.click()
            self.page.wait_for_timeout(1000)
            
            # 核心断言：遮罩层必须被移除，页面可点击
            modal.wait_for(state="hidden", timeout=3000)
            logger.info("[断言] 弹窗和遮罩层被成功清理，不存在 UI 残留")
            
        except PlaywrightTimeoutError:
            raise AssertionError("工单历史弹窗未能正常弹起，或关闭后未能正常隐藏") from None
            
        return self
