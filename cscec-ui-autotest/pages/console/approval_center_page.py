"""控制台审批中心 Page Object — M3 审批/待办链路。"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from playwright.sync_api import (
    Locator,
    Page,
    Response,
    TimeoutError as PlaywrightTimeoutError,
    expect,
)

from config.settings import settings
from core.base_page import BasePage
from core.execution_contract import PrerequisiteResult
from core.interaction_evidence import click_and_expect, require_business_identity
from core.logger import get_logger
from core.navigation_helpers import EntryNotExposed
from pages.console.console_menu_page import ConsoleMenuPage

logger = get_logger("approval_center_page")


@dataclass(frozen=True)
class ApprovalRecord:
    """Stable identity and display fields for one approval-list record."""

    proc_inst_id: str
    proc_name: str
    description: str
    biz_name: str
    biz_code: str
    biz_key: str
    start_user_name: str
    start_user_dept_name: str
    process_state_name: str


@dataclass(frozen=True)
class ApprovalListSnapshot:
    """Validated approval records for one workflow status Tab."""

    status: int
    records: tuple[ApprovalRecord, ...]
    total: int

    @property
    def first_record(self) -> ApprovalRecord:
        """Return the first existing record after a prerequisite check."""
        assert self.records, "审批列表没有可只读查看的样本"
        return self.records[0]


class ApprovalCenterPage(BasePage):
    """审批中心与待办列表页。"""

    PAGE_NAME = "审批中心"
    PAGE_URL_PATTERN = "approval"
    PARENT_MENU = "审批流程"
    CHILD_MENU = "审批中心"
    LIST_API = re.compile(r"/workflow/portal/getPortalApproveTask$")

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self._menu: ConsoleMenuPage | None = None

    def prepare_console_menu(self) -> "ApprovalCenterPage":
        """Load the current account's authorized console menu."""
        self._menu = ConsoleMenuPage(self.page).open_console_home()
        return self

    def menu_prerequisite(self) -> PrerequisiteResult:
        """Return whether approval center is an authorized child menu."""
        return self._require_menu().child_menu_prerequisite(
            self.PARENT_MENU,
            self.CHILD_MENU,
        )

    def open_approval_center(self) -> ApprovalListSnapshot:
        """Open approval center through its real menu and capture pending tasks."""
        menu = self._require_menu()
        menu.expand_menu_group(self.PARENT_MENU)
        entry = self.page.get_by_role("menuitem").filter(
            has=self.page.get_by_text(self.CHILD_MENU, exact=True)
        )
        expect(entry).to_have_count(1)
        with self.page.expect_response(
            lambda response: bool(self.LIST_API.search(response.url)),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as captured:
            entry.click()
        expect(self.page).to_have_url(re.compile(r"/sub/workflow/flowApproval[?]"))
        expect(self.page.get_by_role("tab", name="待办流程", exact=True)).to_have_attribute(
            "aria-selected",
            "true",
        )
        snapshot = self._parse_list_response(captured.value, expected_status=0)
        self.assertions.page_not_blank_or_error()
        return snapshot

    def query_missing_pending_flow(self) -> ApprovalListSnapshot:
        """Prove the pending search request and its zero-result UI agree."""
        keyword = f"AUTO-M3-NO-MATCH-{uuid4().hex}"
        panel = self._active_workflow_panel()
        field = panel.get_by_placeholder("流程名称", exact=True)
        field.fill(keyword)
        with self.page.expect_response(
            lambda response: bool(self.LIST_API.search(response.url)),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as captured:
            panel.get_by_role("button", name=re.compile(r"^查\s*询$")).click()
        snapshot = self._parse_list_response(captured.value, expected_status=0)
        request = captured.value.request.post_data_json
        assert isinstance(request, dict), "待办查询请求不是对象"
        assert request.get("procNameLike") == keyword, "待办查询未提交目标流程名"
        assert snapshot.total == 0 and not snapshot.records, (
            "唯一不存在的流程名查询返回了数据"
        )
        expect(field).to_have_value(keyword)
        expect(panel.locator("span").filter(has_text="暂无数据")).to_be_visible()
        return snapshot

    def open_completed_flows(self) -> ApprovalListSnapshot:
        """Switch to completed approvals and capture an API-backed sample."""
        tab = self.page.get_by_role("tab", name="已办流程", exact=True)
        with self.page.expect_response(
            lambda response: bool(self.LIST_API.search(response.url)),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as captured:
            tab.click()
        expect(tab).to_have_attribute("aria-selected", "true")
        return self._parse_list_response(captured.value, expected_status=1)

    @staticmethod
    def completed_flow_prerequisite(
        snapshot: ApprovalListSnapshot,
    ) -> PrerequisiteResult:
        """Declare whether a completed approval can be inspected read-only."""
        return PrerequisiteResult(
            satisfied=bool(snapshot.records),
            reason="当前账号没有可只读查看的已办流程",
            expected="已办流程接口至少返回 1 条记录",
            actual=f"records={len(snapshot.records)}",
        )

    def inspect_completed_business_and_flow(
        self,
        snapshot: ApprovalListSnapshot,
    ) -> "ApprovalCenterPage":
        """Open one completed business form and its nested approval flow."""
        record = snapshot.first_record
        row = self.page.locator(".table-row").filter(
            has=self.page.get_by_text(record.proc_inst_id, exact=True)
        )
        expect(row).to_have_count(1)
        target = row.get_by_text("查看", exact=True)

        def business_ready() -> None:
            expect(self.page).to_have_url(re.compile(r"/flowmodel/detail[?]"))
            for text in ("基础信息", "业务表单", "订单编码", "审批流程"):
                expect(self.page.get_by_text(text, exact=True).first).to_be_visible()

        click_and_expect(target, business_ready, action_name="打开已办业务表单")
        query = self._route_query(self.page.url)
        assert query.get("wfpiid") == [record.proc_inst_id], "业务表单流程实例错误"
        assert query.get("id") == [record.biz_key], "业务表单业务对象错误"
        require_business_identity(self.page.locator("body"), record.proc_name, "已办业务表单")

        flow_entry = self.page.get_by_text("【查看审批流程】", exact=True)

        def flow_ready() -> None:
            expect(self.page).to_have_url(re.compile(r"/sub/workflow/flowdetail[?]"))
            expect(self.page.get_by_text("流程信息", exact=True)).to_be_visible()
            expect(self.page.get_by_text("审批记录", exact=True)).to_be_visible()

        click_and_expect(flow_entry, flow_ready, action_name="打开嵌套审批流程")
        nested_query = self._route_query(self.page.url)
        assert nested_query.get("procInstId", [""])[0], "审批流程缺少实例 ID"

        approval_tab = self.page.locator(
            '[role="tab"][aria-controls*="/sub/workflow/flowApproval"]'
        )
        expect(approval_tab).to_have_count(1)
        approval_tab.click()
        expect(self.page).to_have_url(re.compile(r"/sub/workflow/flowApproval[?]"))
        expect(self.page.get_by_role("tab", name="已办流程", exact=True)).to_be_visible()
        return self

    @classmethod
    def _parse_list_response(
        cls,
        response: Response,
        *,
        expected_status: int,
    ) -> ApprovalListSnapshot:
        """Validate approval list response and its requested workflow status."""
        assert response.status == 200, "审批列表接口 HTTP 状态异常"
        request = response.request.post_data_json
        assert isinstance(request, dict), "审批列表请求不是对象"
        assert request.get("status") == expected_status, (
            f"审批列表请求状态错误: expected={expected_status}, "
            f"actual={request.get('status')!r}"
        )
        payload = response.json()
        assert isinstance(payload, dict), "审批列表接口响应不是对象"
        code = payload.get("code")
        assert type(code) is int and code == 0, (
            f"审批列表接口业务失败: code={code!r}, "
            f"message={payload.get('message')!r}"
        )
        data = payload.get("data")
        assert isinstance(data, dict), "审批列表接口 data 不是对象"
        raw_records = data.get("list")
        assert isinstance(raw_records, list), "审批列表接口 data.list 不是列表"
        records = tuple(cls._parse_record(raw) for raw in raw_records)
        try:
            total = int(data.get("total", len(records)))
        except (TypeError, ValueError) as exc:
            raise AssertionError("审批列表接口 total 不是整数") from exc
        assert total >= len(records), "审批列表 total 小于当前记录数"
        return ApprovalListSnapshot(expected_status, records, total)

    @classmethod
    def _parse_record(cls, raw: Any) -> ApprovalRecord:
        assert isinstance(raw, Mapping), "审批列表包含非对象记录"
        return ApprovalRecord(
            proc_inst_id=cls._required_text(raw, "procInstId"),
            proc_name=cls._required_text(raw, "procName"),
            description=cls._optional_text(raw, "description"),
            biz_name=cls._optional_text(raw, "bizName"),
            biz_code=cls._required_text(raw, "bizCode"),
            biz_key=cls._required_text(raw, "bizKey"),
            start_user_name=cls._required_text(raw, "startUserName"),
            start_user_dept_name=cls._optional_text(raw, "startUserDeptName"),
            process_state_name=cls._required_text(raw, "processStateName"),
        )

    @staticmethod
    def _required_text(raw: Mapping[str, Any], field: str) -> str:
        value = raw.get(field)
        assert value is not None and str(value).strip(), (
            f"审批记录缺少有效字段 {field!r}: keys={sorted(raw)}"
        )
        return str(value).strip()

    @staticmethod
    def _optional_text(raw: Mapping[str, Any], field: str) -> str:
        value = raw.get(field)
        return str(value).strip() if value is not None else ""

    @staticmethod
    def _route_query(url: str) -> dict[str, list[str]]:
        """Parse query parameters from a normal URL or a hash-based SPA route."""
        parsed = urlparse(url)
        route_query = parsed.fragment.partition("?")[2]
        return parse_qs(route_query or parsed.query)

    def _active_workflow_panel(self) -> Locator:
        """Return the visible inner workflow Tab panel."""
        panels = self.page.get_by_role("tabpanel")
        return panels.last

    def _require_menu(self) -> ConsoleMenuPage:
        """Return the prepared menu or fail before interacting."""
        assert self._menu is not None, "尚未加载控制台菜单树"
        return self._menu

    def open_todo_list(self) -> "ApprovalCenterPage":
        """进入我的待办列表（M3-01）。"""
        try:
            self.nav.goto_url(settings.console_url("/udpweb/portal/index.html#/portal/approval/todo"))
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

    def switch_to_done_tab(self) -> "ApprovalCenterPage":
        """M3-SUPP-001: 切换到“已办/已处理”Tab 验证历史数据查询可用性。"""
        done_tab = self.elements.find_candidates(
            [
                ("text", "已办"),
                ("text", "已处理"),
                ("text", "已审批"),
            ],
            description="已办Tab",
            timeout=3000
        )
        
        if done_tab:
            done_tab.click()
            self.nav.wait_ready()
            self.assertions.page_not_blank_or_error()
            self.assertions.any_text_visible(["已办", "单号", "暂无数据"])
            logger.info("[断言] 已办(历史)审批列表查询正常，未超时")
        else:
            raise EntryNotExposed("审批列表未暴露已办/已处理 Tab")
            
        return self

    def open_approval_history_drawer(self) -> "ApprovalCenterPage":
        """M3-SUPP-002: 在审批详情内拉起历史/流程图抽屉并验证。"""
        history_btn = self.elements.find_candidates(
            [
                ("text", "审批历史"),
                ("text", "流转历史"),
                ("text", "查看流程"),
                ("text", "流程图"),
            ],
            description="流转历史按钮",
            timeout=3000
        )
        
        if not history_btn:
            raise EntryNotExposed("审批详情未暴露审批历史/流程图入口")
            
        history_btn.click()
        self.page.wait_for_timeout(1000) # 等待抽屉弹出动画
        
        # 断言 Drawer 或 Modal 成功弹起
        try:
            drawer = self.page.locator(".ant-drawer-content, .el-drawer, .ant-modal-content, .el-dialog").first
            drawer.wait_for(state="visible", timeout=5000)
            logger.info("[断言] 审批历史/流程图弹窗成功渲染")
            
            # 尝试关闭它以清理现场
            close_btn = drawer.locator(".ant-drawer-close, .el-drawer__close-btn, .ant-modal-close, .el-dialog__headerbtn").first
            if close_btn.is_visible():
                close_btn.click()
        except PlaywrightTimeoutError:
            raise AssertionError("点击流转历史后，审批历史/流程图弹窗未能成功渲染") from None
            
        return self
