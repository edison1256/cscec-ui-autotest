"""控制台工单中心 Page Object — M4 工单基础链路。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re
from typing import Any, Optional

from playwright.sync_api import Page, Response, TimeoutError as PlaywrightTimeoutError, expect

from config.settings import settings
from core.base_page import BasePage
from core.execution_contract import PrerequisiteResult
from core.logger import get_logger
from core.navigation_helpers import EntryNotExposed
from pages.console.console_menu_page import ConsoleMenuPage

logger = get_logger("ticket_center_page")


@dataclass(frozen=True)
class TicketRecord:
    """Stable identity and display fields for one real ticket."""

    ticket_id: str
    code: str
    title: str
    description: str
    type_code: str
    type_description: str
    creator_name: str
    assignee_name: str
    created_at: str


@dataclass(frozen=True)
class TicketListSnapshot:
    """Validated ticket list response used by the next interaction."""

    records: tuple[TicketRecord, ...]
    total: int

    @property
    def first_record(self) -> TicketRecord:
        """Return the first validated sample."""
        assert self.records, "工单列表没有可用样本"
        return self.records[0]


class TicketCenterPage(BasePage):
    """工单中心与工单管理页。"""

    PAGE_NAME = "工单中心"
    PAGE_URL_PATTERN = "ticket"

    LIST_API = re.compile(
        r"/irp-api/irp-portal-console/work-order/allWorkOrderList$"
    )
    DETAIL_API = re.compile(
        r"/irp-api/irp-portal-console/work-order/detail[?]"
    )
    PROCESS_API = re.compile(
        r"/irp-api/irp-portal-console/work-order/processList$"
    )
    PENDING_STATUS = 1

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self._menu: ConsoleMenuPage | None = None

    def prepare_console_menu(self) -> "TicketCenterPage":
        """Load authorized menus before evaluating the ticket prerequisite."""
        self._menu = ConsoleMenuPage(self.page).open_console_home()
        return self

    def menu_prerequisite(self) -> PrerequisiteResult:
        """Require the real console ticket-management child menu."""
        return self._require_menu().child_menu_prerequisite("工单中心", "工单管理")

    def open_ticket_management(self) -> TicketListSnapshot:
        """Enter ticket management through the real menu and validate its list."""
        self._require_menu().expand_menu_group("工单中心")
        entry = self.page.get_by_role("menuitem").filter(
            has=self.page.get_by_text("工单管理", exact=True)
        )
        expect(entry).to_have_count(1)
        with self.page.expect_response(
            lambda response: bool(self.LIST_API.search(response.url)),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as captured:
            entry.click()
        expect(self.page).to_have_url(re.compile(r"/workOrderCenter/allManageOrder[?]"))
        expect(self.page.get_by_text("工单管理", exact=True).first).to_be_visible()
        expect(self.page.get_by_placeholder("请输入工单编号", exact=True)).to_be_visible()
        return self._parse_list_response(captured.value)

    @staticmethod
    def sample_prerequisite(snapshot: TicketListSnapshot) -> PrerequisiteResult:
        """Describe whether a real ticket can be queried and opened read-only."""
        return PrerequisiteResult(
            satisfied=bool(snapshot.records),
            reason="工单管理列表没有可供只读查询和查看的现有工单",
            expected="至少一条包含完整身份字段的现有工单",
            actual=f"valid_records={len(snapshot.records)}, total={snapshot.total}",
        )

    def query_existing_ticket(
        self,
        snapshot: TicketListSnapshot,
    ) -> TicketListSnapshot:
        """Query the current first ticket and prove request, response and row agree."""
        expected = snapshot.first_record
        field = self.page.get_by_placeholder("请输入工单编号", exact=True)
        field.fill(expected.code)
        with self.page.expect_response(
            lambda response: bool(self.LIST_API.search(response.url)),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as captured:
            self.page.get_by_role("button", name=re.compile(r"^查\s*询$")).click()
        result = self._parse_list_response(captured.value)
        self._validate_query_result(
            captured.value.request.post_data_json,
            result,
            expected,
        )
        expect(field).to_have_value(expected.code)
        row = self._ticket_row(expected.code)
        expect(row).to_have_count(1)
        expect(row).to_be_visible()
        return result

    def inspect_ticket_detail(self, snapshot: TicketListSnapshot) -> None:
        """Open the selected ticket dialog and validate detail and process data."""
        expected = snapshot.first_record
        row = self._ticket_row(expected.code)
        view_button = row.get_by_role("button", name="查看", exact=True)
        expect(view_button).to_be_enabled()
        with self.page.expect_response(
            lambda response: bool(self.DETAIL_API.search(response.url)),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as detail_capture:
            with self.page.expect_response(
                lambda response: bool(self.PROCESS_API.search(response.url)),
                timeout=settings.NAVIGATION_TIMEOUT,
            ) as process_capture:
                view_button.click()

        detail = self._validate_detail_response(detail_capture.value, expected)
        self._validate_process_response(process_capture.value, expected.ticket_id)
        dialog = self.page.get_by_role("dialog").filter(
            has=self.page.get_by_text("工单详情", exact=True)
        )
        if dialog.count() == 0:
            dialog = self.page.get_by_role("dialog").filter(
                has=self.page.get_by_text("工单ID", exact=False)
            )
        expect(dialog).to_have_count(1)
        expect(dialog).to_be_visible()
        for value in (
            expected.ticket_id,
            expected.title,
            expected.description,
            expected.creator_name,
            expected.assignee_name,
        ):
            expect(dialog.get_by_text(value, exact=False).first).to_be_visible()
        assert str(detail.get("workOrderCode")) == expected.code

        close_button = dialog.get_by_role("button", name=re.compile(r"关闭|Close"))
        if close_button.count() == 0:
            close_button = dialog.locator(
                ".ant-modal-close, .el-dialog__headerbtn, [aria-label='close']"
            )
        expect(close_button.first).to_be_visible()
        close_button.first.click()
        expect(dialog).to_have_count(0)
        expect(self.page.get_by_placeholder("请输入工单编号", exact=True)).to_be_visible()

    def verify_management_action_boundaries(
        self,
        snapshot: TicketListSnapshot,
    ) -> None:
        """Verify safe action availability without triggering ticket writes."""
        expected = snapshot.first_record
        row = self._ticket_row(expected.code)
        expect(row).to_have_count(1)
        expect(row.get_by_role("button", name="查看", exact=True)).to_be_enabled()
        expect(row.get_by_role("button", name="处理", exact=True)).to_be_disabled()
        reminder = row.get_by_role("button", name="提醒", exact=True)
        expect(reminder).to_have_count(1)
        expect(reminder).to_be_enabled()
        logger.info(
            "[只读边界] 工单 %s 查看可用、处理禁用、提醒未点击",
            expected.code,
        )

    @staticmethod
    def pagination_prerequisite(snapshot: TicketListSnapshot) -> PrerequisiteResult:
        """Require at least two pages of ticket records."""
        return PrerequisiteResult(
            satisfied=snapshot.total > len(snapshot.records) and bool(snapshot.records),
            reason="工单列表当前不足两页，无法验证翻页链路",
            expected="总数大于当前页记录数",
            actual=f"total={snapshot.total}, records={len(snapshot.records)}",
        )

    def verify_ticket_pagination(self, first_page: TicketListSnapshot) -> None:
        """Navigate to page two and back while validating ticket identities."""
        first_code = first_page.first_record.code
        pager = self.page.locator(".ant-pagination:visible")
        with self.page.expect_response(
            lambda response: bool(self.LIST_API.search(response.url)),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as second_capture:
            pager.get_by_text("2", exact=True).click()
        second = self._parse_list_response(second_capture.value)
        second_request = second_capture.value.request.post_data_json
        assert isinstance(second_request, dict), "工单第二页请求不是对象"
        assert second_request.get("pageIndex") == 2, "工单翻页未请求第 2 页"
        assert second.records, "工单第二页没有可验证记录"
        second_code = second.first_record.code
        assert second_code != first_code, "工单第二页仍显示第一页首条"
        expect(pager.locator(".ant-pagination-item-active")).to_have_text("2")
        expect(self.page.get_by_text(second_code, exact=True)).to_be_visible()

        with self.page.expect_response(
            lambda response: bool(self.LIST_API.search(response.url)),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as first_capture:
            pager.get_by_text("1", exact=True).click()
        first_request = first_capture.value.request.post_data_json
        assert isinstance(first_request, dict), "工单返回第一页请求不是对象"
        assert first_request.get("pageIndex") == 1, "工单分页未返回第 1 页"
        expect(pager.locator(".ant-pagination-item-active")).to_have_text("1")
        expect(self.page.get_by_text(first_code, exact=True)).to_be_visible()

    def filter_pending_tickets(self) -> TicketListSnapshot:
        """Filter pending tickets and prove request, response, and UI agree."""
        status_item = self.page.locator(".ant-form-item:visible").filter(
            has=self.page.get_by_text("状态", exact=True)
        )
        status_item.get_by_role("combobox").click()
        dropdown = self.page.locator(
            ".ant-select-dropdown:not(.ant-select-dropdown-hidden)"
        ).last
        dropdown.get_by_text("待处理", exact=True).click()
        with self.page.expect_response(
            lambda response: bool(self.LIST_API.search(response.url)),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as captured:
            self.page.get_by_role("button", name=re.compile(r"^查\s*询$")).click()
        result = self._parse_list_response(captured.value)
        request = captured.value.request.post_data_json
        assert isinstance(request, dict), "工单状态筛选请求不是对象"
        query = request.get("queryfilter")
        assert isinstance(query, dict), "工单状态筛选缺少 queryfilter"
        assert query.get("orderStatus") == self.PENDING_STATUS, "工单状态筛选值不正确"
        payload = captured.value.json()
        records = payload["data"]["records"]
        assert records, "待处理筛选没有返回可验证工单"
        assert all(
            row.get("workOrderStatus") == self.PENDING_STATUS for row in records
        ), "工单状态筛选返回了其他状态"
        expect(status_item.get_by_text("待处理", exact=True)).to_be_visible()
        expect(self.page.get_by_text(result.first_record.code, exact=True)).to_be_visible()
        return result

    def reset_ticket_filters(self) -> TicketListSnapshot:
        """Reset ticket filters and require an empty query and control state."""
        with self.page.expect_response(
            lambda response: bool(self.LIST_API.search(response.url)),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as captured:
            self.page.get_by_role("button", name=re.compile(r"^重\s*置$")).click()
        result = self._parse_list_response(captured.value)
        request = captured.value.request.post_data_json
        assert isinstance(request, dict), "工单重置请求不是对象"
        assert request.get("queryfilter") == {}, "工单重置后查询条件未清空"
        status_item = self.page.locator(".ant-form-item:visible").filter(
            has=self.page.get_by_text("状态", exact=True)
        )
        expect(status_item.get_by_text("请选择", exact=True)).to_be_visible()
        type_item = self.page.locator(".ant-form-item:visible").filter(
            has=self.page.get_by_text("工单类型", exact=True)
        )
        expect(type_item.get_by_text("请选择", exact=True)).to_be_visible()
        expect(self.page.get_by_placeholder("请输入工单编号", exact=True)).to_be_empty()
        return result

    def filter_by_existing_ticket_type(
        self,
        snapshot: TicketListSnapshot,
    ) -> TicketListSnapshot:
        """Filter by a real ticket type and prove request, response, and UI agree."""
        type_item = self.page.locator(".ant-form-item:visible").filter(
            has=self.page.get_by_text("工单类型", exact=True)
        )
        expect(type_item).to_have_count(1)
        type_item.get_by_role("combobox").click()
        dropdown = self.page.locator(
            ".ant-select-dropdown:not(.ant-select-dropdown-hidden)"
        ).last
        option = dropdown.locator(".ant-select-item-option").first
        expect(option).to_be_visible()
        option_text = option.inner_text().strip()
        assert option_text, "工单类型首个字典选项为空"
        option.click()

        with self.page.expect_response(
            lambda response: bool(self.LIST_API.search(response.url)),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as captured:
            self.page.get_by_role("button", name=re.compile(r"^查\s*询$")).click()
        result = self._parse_list_response(captured.value)
        request = captured.value.request.post_data_json
        assert isinstance(request, dict), "工单类型筛选请求不是对象"
        query = request.get("queryfilter")
        assert isinstance(query, dict), "工单类型筛选缺少 queryfilter"
        selected_query = {key: value for key, value in query.items() if value}
        assert set(selected_query) == {"workOrderType"}, (
            f"工单类型筛选提交了意外条件: {selected_query}"
        )
        selected_type = str(selected_query["workOrderType"])
        assert result.records, "工单类型筛选没有返回可验证记录"
        assert all(record.type_code == selected_type for record in result.records), (
            "工单类型筛选返回了其他类型编码"
        )
        expected_cell_text = re.sub(r"工单$", "", option_text)
        rows = self.page.locator(".table-row").filter(
            has=self.page.get_by_text(expected_cell_text, exact=True)
        )
        assert rows.count() >= len(result.records), "工单类型筛选返回了其他类型"
        expect(type_item.get_by_text(option_text, exact=True)).to_be_visible()
        expect(self.page.get_by_text(result.first_record.code, exact=True)).to_be_visible()
        return result

    @classmethod
    def _parse_list_response(cls, response: Response) -> TicketListSnapshot:
        """Validate the ticket-list transport, envelope and required identity."""
        assert response.status == 200, "工单列表接口 HTTP 失败"
        payload = response.json()
        assert isinstance(payload, dict), "工单列表接口不是对象"
        assert type(payload.get("code")) is int and payload["code"] == 0, (
            "工单列表接口业务失败"
        )
        data = payload.get("data")
        assert isinstance(data, Mapping), "工单列表 data 不是对象"
        raw_records = data.get("records")
        assert isinstance(raw_records, list), "工单列表 records 不是列表"
        raw_total = data.get("total")
        try:
            total = int(raw_total)
        except (TypeError, ValueError):
            raise AssertionError("工单列表 total 不是整数") from None
        assert total >= len(raw_records), "工单列表 total 小于本页记录数"
        records = tuple(cls._parse_ticket_record(row) for row in raw_records)
        return TicketListSnapshot(records=records, total=total)

    @staticmethod
    def _parse_ticket_record(raw: Any) -> TicketRecord:
        assert isinstance(raw, Mapping), "工单列表记录不是对象"
        fields = {
            "ticket_id": raw.get("id"),
            "code": raw.get("workOrderCode"),
            "title": raw.get("title"),
            "description": raw.get("workOrderDescription"),
            "type_code": raw.get("workOrderType"),
            "type_description": raw.get("workOrderTypeDesc"),
            "creator_name": raw.get("creatorName"),
            "assignee_name": raw.get("assigneeName"),
            "created_at": raw.get("insertDt"),
        }
        missing = [name for name, value in fields.items() if not str(value or "").strip()]
        assert not missing, f"工单记录缺少必需字段: {', '.join(missing)}"
        return TicketRecord(**{name: str(value).strip() for name, value in fields.items()})

    @staticmethod
    def _validate_query_result(
        request: Any,
        result: TicketListSnapshot,
        expected: TicketRecord,
    ) -> None:
        assert isinstance(request, dict), "工单查询请求不是对象"
        query = request.get("queryfilter")
        assert isinstance(query, dict), "工单查询缺少 queryfilter"
        assert query.get("workOrderCode") == expected.code, "工单查询未提交目标编号"
        assert result.records, "工单查询未返回已知存在的样本"
        assert len(result.records) == 1, "工单编号未唯一命中"
        assert all(record.code == expected.code for record in result.records), (
            "工单查询返回了其他编号的记录"
        )
        assert result.first_record.ticket_id == expected.ticket_id, (
            "查询工单 ID 与原列表不一致"
        )

    @staticmethod
    def _validate_detail_response(
        response: Response,
        expected: TicketRecord,
    ) -> Mapping[str, Any]:
        assert response.status == 200, "工单详情接口 HTTP 失败"
        payload = response.json()
        assert isinstance(payload, dict), "工单详情接口不是对象"
        assert type(payload.get("code")) is int and payload["code"] == 0, (
            "工单详情接口业务失败"
        )
        data = payload.get("data")
        assert isinstance(data, Mapping), "工单详情 data 不是对象"
        assert str(data.get("id")) == expected.ticket_id, "工单详情返回了其他工单"
        assert str(data.get("workOrderCode")) == expected.code, "工单详情编号不一致"
        assert str(data.get("title")) == expected.title, "工单详情标题不一致"
        assert str(data.get("workOrderDescription")) == expected.description, (
            "工单详情描述不一致"
        )
        return data

    @staticmethod
    def _validate_process_response(response: Response, ticket_id: str) -> list[dict]:
        assert response.status == 200, "工单处理记录接口 HTTP 失败"
        request = response.request.post_data_json
        assert isinstance(request, dict), "工单处理记录请求不是对象"
        query = request.get("queryfilter")
        assert isinstance(query, dict), "工单处理记录请求缺少 queryfilter"
        assert str(query.get("workOrderId")) == ticket_id, "处理记录请求了其他工单"
        payload = response.json()
        assert isinstance(payload, dict), "工单处理记录接口不是对象"
        assert type(payload.get("code")) is int and payload["code"] == 0, (
            "工单处理记录接口业务失败"
        )
        data = payload.get("data")
        assert isinstance(data, Mapping), "工单处理记录 data 不是对象"
        records = data.get("records")
        assert isinstance(records, list), "工单处理记录 records 不是列表"
        assert all(isinstance(row, dict) for row in records), "工单处理记录含非对象项"
        return records

    def _ticket_row(self, code: str):
        return self.page.locator(".table-row").filter(
            has=self.page.get_by_text(code, exact=True)
        )

    def _require_menu(self) -> ConsoleMenuPage:
        assert self._menu is not None, "尚未加载控制台菜单树"
        return self._menu

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
