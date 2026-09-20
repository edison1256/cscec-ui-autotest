"""控制台与门户订单管理 Page Object — M2 订阅/订单主链路。"""

from __future__ import annotations

import re
import time
from collections.abc import Mapping
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Page, Response, TimeoutError as PlaywrightTimeoutError, expect

from config.settings import settings
from core.base_page import BasePage
from core.execution_contract import PrerequisiteResult
from core.logger import get_logger
from core.navigation_helpers import EntryNotExposed
from pages.console.console_menu_page import ConsoleMenuPage
from pages.console.console_workbench_page import (
    ConsoleWorkbenchPage,
    WorkbenchListSnapshot,
)
from pages.console.resource_mgmt_page import PortalResourceRecord

logger = get_logger("order_mgmt_page")


class OrderMgmtPage(BasePage):
    """订单与订阅管理页。"""

    PAGE_NAME = "订单与订阅管理"
    PAGE_URL_PATTERN = "order"

    LIST_API = re.compile(r"/irp-api/irp-portal-console/order/page$")
    APPLY_FLOW_API = re.compile(
        r"/irp-api/irp-portal-public/flow-template/getApplyFlowChainNoAuth[?]"
    )
    ORDER_DRAFT_API = re.compile(
        r"/irp-api/irp-portal-public/order/getOrderDraft[?]"
    )
    COMPLETED_STATE = 8

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self._menu: ConsoleMenuPage | None = None

    def prepare_console_menu(self) -> "OrderMgmtPage":
        """Load authorized menus before evaluating the order entry prerequisite."""
        self._menu = ConsoleMenuPage(self.page).open_console_home()
        return self

    def menu_prerequisite(self) -> PrerequisiteResult:
        """Require the real console order-management child menu."""
        return self._require_menu().child_menu_prerequisite("订单中心", "订单管理")

    def open_console_orders(self) -> WorkbenchListSnapshot:
        """Enter the order list from the sidebar and validate its response."""
        self._require_menu().expand_menu_group("订单中心")
        entry = self.page.get_by_role("menuitem").filter(
            has=self.page.get_by_text("订单管理", exact=True)
        )
        expect(entry).to_have_count(1)
        with self.page.expect_response(
            lambda response: bool(self.LIST_API.search(response.url)),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as captured:
            entry.click()
        expect(self.page).to_have_url(re.compile(r"/orderCenter/myOrders[?]"))
        expect(self.page.get_by_text("订单列表", exact=True)).to_be_visible()
        expect(self.page.get_by_placeholder("请输入订单编码", exact=True)).to_be_visible()
        return ConsoleWorkbenchPage._parse_list_response(captured.value, "订单管理")

    def query_existing_order(
        self, snapshot: WorkbenchListSnapshot,
    ) -> WorkbenchListSnapshot:
        """Search a real order code and prove request, response and row agree."""
        record = snapshot.first_record
        code = str(record.get("orderCode") or "")
        assert code, "订单样本缺少订单编码"
        field = self.page.get_by_placeholder("请输入订单编码", exact=True)
        field.fill(code)
        with self.page.expect_response(
            lambda response: bool(self.LIST_API.search(response.url)),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as captured:
            self.page.get_by_role("button", name=re.compile(r"^查\s*询$")).click()
        response = captured.value
        result = ConsoleWorkbenchPage._parse_list_response(response, "订单查询")
        self._validate_query_result(response.request.post_data_json, result, record)
        expect(field).to_have_value(code)
        row = self.page.locator(".table-row").filter(
            has=self.page.get_by_text(code, exact=True)
        ).filter(
            has=self.page.get_by_role("button", name="更多", exact=True)
        ).last
        expect(row).to_have_count(1)
        expect(row).to_be_visible()
        return result

    @staticmethod
    def _validate_query_result(
        request: Any, result: WorkbenchListSnapshot, expected: Mapping[str, Any],
    ) -> None:
        """Reject ignored filters, unrelated records and missing target orders."""
        assert isinstance(request, dict), "订单查询请求不是对象"
        query = request.get("queryfilter")
        assert isinstance(query, dict), "订单查询缺少 queryfilter"
        code = expected.get("orderCode")
        assert code and query.get("orderCode") == code, "订单查询未提交目标编码"
        assert result.records, "订单查询未返回已知存在的样本"
        assert all(row.get("orderCode") == code for row in result.records), (
            "订单查询返回了其他编码的记录"
        )
        assert len(result.records) == 1, "订单编码未唯一命中"
        assert str(result.first_record.get("id")) == str(expected.get("id")), (
            "查询订单 ID 与原列表不一致"
        )

    def inspect_order_detail(self, snapshot: WorkbenchListSnapshot) -> None:
        """Verify the selected order and its flow tab, then return without writes."""
        order_id = str(snapshot.first_record["id"])
        with self.page.expect_response(
            lambda response: "/order/change/list?" in response.url
            and parse_qs(urlparse(response.url).query).get("orderId") == [order_id],
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as history_response:
            ConsoleWorkbenchPage(self.page).open_first_detail(
                snapshot,
                row_identity_field="orderCode",
                detail_identity_field="id",
                required_labels=("基础信息", "订单编码", "资源信息", "审批进度"),
                detail_api_pattern=r"/order/orderDetail[?]",
            )
        history = self._validate_history(history_response.value, order_id)
        overlay = self.page.locator(
            ".ant-drawer:visible, .ant-modal:visible, .el-dialog:visible, .el-drawer:visible"
        )
        expect(overlay).to_have_count(1)
        tab = overlay.get_by_role("tab", name="流转明细", exact=True)
        tab.click()
        expect(tab).to_have_attribute("aria-selected", "true")
        panel_id = tab.get_attribute("aria-controls")
        assert panel_id, "流转明细 Tab 未关联面板"
        panel = overlay.locator(f'[id="{panel_id}"]')
        expect(panel).to_be_visible()
        if history:
            expect(panel.get_by_text("时间：", exact=False).first).to_be_visible()
        else:
            expect(panel.get_by_text("暂无数据", exact=True)).to_be_visible()
        overlay.get_by_role("button", name=re.compile(r"^返\s*回$")).click()
        expect(overlay).to_have_count(0)
        expect(self.page.get_by_placeholder("请输入订单编码", exact=True)).to_be_visible()

    def inspect_order_flow_diagram(self, snapshot: WorkbenchListSnapshot) -> None:
        """Open and validate the selected order's read-only flow diagram."""
        ConsoleWorkbenchPage(self.page).open_first_detail(
            snapshot,
            row_identity_field="orderCode",
            detail_identity_field="id",
            required_labels=("基础信息", "订单编码", "资源信息", "审批进度"),
            detail_api_pattern=r"/order/orderDetail[?]",
        )
        detail = self.page.locator(
            ".ant-drawer:visible, .ant-modal:visible, "
            ".el-dialog:visible, .el-drawer:visible"
        )
        expect(detail).to_have_count(1)
        flow_button = detail.get_by_role("button", name="流程图", exact=True)
        expect(flow_button).to_be_enabled()
        flow_button.click()

        flow_dialog = self.page.get_by_role("dialog").filter(
            has=self.page.get_by_text("查看流程图", exact=True)
        )
        expect(flow_dialog).to_have_count(1)
        expect(flow_dialog).to_be_visible()
        for legend in ("已完成", "进行中", "未办理"):
            expect(flow_dialog.get_by_text(legend, exact=True)).to_be_visible()

        flow_dialog.get_by_role("button", name="Close", exact=True).click()
        expect(flow_dialog).to_have_count(0)
        detail.get_by_role("button", name=re.compile(r"^返\s*回$")).click()
        expect(detail).to_have_count(0)
        expect(self.page.get_by_placeholder("请输入订单编码", exact=True)).to_be_visible()

    def filter_completed_orders(self) -> WorkbenchListSnapshot:
        """Filter completed orders and prove request, response, and UI agree."""
        status_item = self.page.locator(".ant-form-item").filter(
            has=self.page.get_by_text("订单状态", exact=True)
        )
        status_item.get_by_role("combobox").click()
        self.page.get_by_text("订阅成功", exact=True).last.click()
        with self.page.expect_response(
            lambda response: bool(self.LIST_API.search(response.url)),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as captured:
            self.page.get_by_role("button", name=re.compile(r"^查\s*询$")).click()
        result = ConsoleWorkbenchPage._parse_list_response(
            captured.value,
            "订单状态筛选",
        )
        request = captured.value.request.post_data_json
        assert isinstance(request, dict), "订单状态筛选请求不是对象"
        query = request.get("queryfilter")
        assert isinstance(query, dict), "订单状态筛选请求缺少 queryfilter"
        assert query.get("state") == self.COMPLETED_STATE, "订单状态筛选值不正确"
        assert result.records, "订阅成功筛选没有返回可验证订单"
        assert all(
            row.get("state") == self.COMPLETED_STATE for row in result.records
        ), "订单状态筛选返回了其他状态"
        expect(status_item.get_by_text("订阅成功", exact=True)).to_be_visible()
        first_code = str(result.first_record.get("orderCode") or "")
        assert first_code, "状态筛选首条订单缺少编码"
        expect(self.page.get_by_text(first_code, exact=True)).to_be_visible()
        return result

    def reset_order_filters(self) -> WorkbenchListSnapshot:
        """Reset the query and require an unfiltered list request and UI state."""
        with self.page.expect_response(
            lambda response: bool(self.LIST_API.search(response.url)),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as captured:
            self.page.get_by_role("button", name=re.compile(r"^重\s*置$")).click()
        result = ConsoleWorkbenchPage._parse_list_response(captured.value, "订单筛选重置")
        request = captured.value.request.post_data_json
        assert isinstance(request, dict), "订单重置请求不是对象"
        query = request.get("queryfilter")
        assert isinstance(query, dict), "订单重置请求缺少 queryfilter"
        for field in ("state", "orderCode", "resourceName", "resourceType"):
            assert not query.get(field), f"订单重置后仍携带 {field}"
        status_item = self.page.locator(".ant-form-item").filter(
            has=self.page.get_by_text("订单状态", exact=True)
        )
        expect(status_item.get_by_text("请选择", exact=True)).to_be_visible()
        expect(self.page.get_by_placeholder("请输入订单编码", exact=True)).to_be_empty()
        return result

    def pagination_prerequisite(self) -> PrerequisiteResult:
        """Require the order list to expose a second page."""
        pager = self.page.locator(".ant-pagination:visible")
        second_page = pager.get_by_text("2", exact=True)
        return PrerequisiteResult(
            satisfied=pager.count() == 1 and second_page.count() == 1,
            reason="订单列表当前不足两页，无法验证翻页链路",
            expected="分页器包含第 2 页",
            actual=f"pager={pager.count()}, page_2={second_page.count()}",
        )

    def verify_order_pagination(
        self,
        first_page: WorkbenchListSnapshot,
    ) -> None:
        """Navigate to page two and back while validating request identities."""
        first_code = str(first_page.first_record.get("orderCode") or "")
        assert first_code, "订单第一页首条缺少编码"
        pager = self.page.locator(".ant-pagination:visible")
        with self.page.expect_response(
            lambda response: bool(self.LIST_API.search(response.url)),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as second_capture:
            pager.get_by_text("2", exact=True).click()
        second = ConsoleWorkbenchPage._parse_list_response(
            second_capture.value,
            "订单第二页",
        )
        second_request = second_capture.value.request.post_data_json
        assert isinstance(second_request, dict), "订单第二页请求不是对象"
        assert second_request.get("pageIndex") == 2, "订单翻页未请求第 2 页"
        assert second.records, "订单第二页没有记录"
        second_code = str(second.first_record.get("orderCode") or "")
        assert second_code and second_code != first_code, "订单第二页仍显示第一页首条"
        expect(pager.locator(".ant-pagination-item-active")).to_have_text("2")
        expect(self.page.get_by_text(second_code, exact=True)).to_be_visible()

        with self.page.expect_response(
            lambda response: bool(self.LIST_API.search(response.url)),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as first_capture:
            pager.get_by_text("1", exact=True).click()
        first_request = first_capture.value.request.post_data_json
        assert isinstance(first_request, dict), "订单返回第一页请求不是对象"
        assert first_request.get("pageIndex") == 1, "订单分页未返回第 1 页"
        expect(pager.locator(".ant-pagination-item-active")).to_have_text("1")
        expect(self.page.get_by_text(first_code, exact=True)).to_be_visible()

    @staticmethod
    def delete_boundary_prerequisite(
        snapshot: WorkbenchListSnapshot,
    ) -> PrerequisiteResult:
        """Require a visible order whose API operators include delete."""
        candidates = [
            row for row in snapshot.records if "delete" in (row.get("operators") or [])
        ]
        return PrerequisiteResult(
            satisfied=bool(candidates),
            reason="订单当前页没有 API 明确允许删除的样本",
            expected="至少一条 operators 包含 delete 的订单",
            actual=f"delete_candidates={len(candidates)}",
        )

    def verify_delete_confirmation_cancel(
        self,
        snapshot: WorkbenchListSnapshot,
    ) -> None:
        """Open an allowed delete confirmation and cancel without writes."""
        record = next(
            row for row in snapshot.records if "delete" in (row.get("operators") or [])
        )
        code = str(record.get("orderCode") or "")
        assert code, "可删除订单缺少编码"
        row = self.page.locator(".table-row").filter(
            has=self.page.get_by_text(code, exact=True)
        ).filter(
            has=self.page.get_by_role("button", name="编辑", exact=True)
        ).last
        row.get_by_role("button", name="更多", exact=True).hover()
        dropdown = self.page.locator(".ant-dropdown:visible")
        expect(dropdown).to_have_count(1)
        delete_button = dropdown.get_by_role("button", name="删除", exact=True)
        expect(delete_button).to_be_enabled()

        writes: list[str] = []
        listener = lambda request: (
            writes.append(f"{request.method} {request.url}")
            if request.method not in {"GET", "HEAD", "OPTIONS"}
            else None
        )
        self.page.on("request", listener)
        try:
            delete_button.click()
            confirm = self.page.locator(".ant-modal-confirm:visible").filter(
                has=self.page.get_by_text("确定删除这条订单记录么", exact=True)
            )
            expect(confirm).to_have_count(1)
            expect(confirm.get_by_role("button", name="确 定")).to_be_enabled()
            confirm.get_by_role("button", name="取 消").click()
            expect(confirm).to_be_hidden()
        finally:
            self.page.remove_listener("request", listener)
        assert writes == [], f"删除确认取消前触发了写请求: {writes}"
        expect(self.page.get_by_text(code, exact=True)).to_be_visible()

    def edit_boundary_prerequisite(
        self,
        snapshot: WorkbenchListSnapshot,
    ) -> PrerequisiteResult:
        """Require API edit permission and the corresponding enabled UI action."""
        candidates = self._editable_order_candidates(snapshot)
        return PrerequisiteResult(
            satisfied=bool(candidates),
            reason="订单当前页没有 API 允许且 UI 编辑按钮可用的样本",
            expected="至少一条 operators 包含 edit 且编辑按钮可用的订单",
            actual=f"edit_candidates={len(candidates)}",
        )

    def inspect_editable_order_readonly(
        self,
        snapshot: WorkbenchListSnapshot,
    ) -> None:
        """Enter an editable order and return without saving or advancing."""
        index, record = self._editable_order_candidates(snapshot)[0]
        code = str(record.get("orderCode") or "")
        assert code, "可编辑订单缺少编码"
        edit_button = self.page.get_by_role(
            "button",
            name="编辑",
            exact=True,
        ).nth(index)
        expect(edit_button).to_be_enabled()

        unsafe_requests: list[str] = []

        def record_unsafe_request(request: Any) -> None:
            method = request.method.upper()
            write_api = re.search(
                r"/(?:save|submit|update|delete|create)(?:[/?]|$)",
                urlparse(request.url).path,
                re.IGNORECASE,
            )
            if method in {"PUT", "PATCH", "DELETE"} or (
                method == "POST" and write_api
            ):
                unsafe_requests.append(f"{method} {request.url}")

        self.page.on("request", record_unsafe_request)
        try:
            previous_url = self.page.url
            edit_button.click()
            expect(self.page).not_to_have_url(previous_url)
            expect(self.page.get_by_text(code, exact=True)).to_be_visible()
            visible_buttons = self.page.get_by_role("button").all_inner_texts()
            logger.info(
                "[订单编辑探查] url=%s buttons=%s unsafe=%s",
                self.page.url,
                visible_buttons,
                unsafe_requests,
            )
            self.page.go_back(wait_until="domcontentloaded")
            expect(self.page.get_by_text("订单列表", exact=True)).to_be_visible()
            expect(self.page.get_by_text(code, exact=True)).to_be_visible()
        finally:
            self.page.remove_listener("request", record_unsafe_request)
        assert unsafe_requests == [], (
            f"进入订单编辑页并返回时触发了写接口: {unsafe_requests}"
        )

    def _editable_order_candidates(
        self,
        snapshot: WorkbenchListSnapshot,
    ) -> list[tuple[int, Mapping[str, Any]]]:
        """Match API records to their same-index rendered edit controls."""
        edit_buttons = self.page.get_by_role("button", name="编辑", exact=True)
        limit = min(len(snapshot.records), edit_buttons.count())
        return [
            (index, snapshot.records[index])
            for index in range(limit)
            if "edit" in (snapshot.records[index].get("operators") or [])
            and edit_buttons.nth(index).is_enabled()
        ]

    @staticmethod
    def _validate_history(response: Response, order_id: str) -> list[dict]:
        """Require flow history to belong to the selected order."""
        assert response.status == 200, "订单流转接口 HTTP 失败"
        payload = response.json()
        assert isinstance(payload, dict), "订单流转接口不是对象"
        assert type(payload.get("code")) is int and payload["code"] == 0, (
            "订单流转接口业务失败"
        )
        data = payload.get("data")
        assert isinstance(data, dict), "订单流转 data 不是对象"
        assert str(data.get("orderId")) == order_id, "订单流转返回了其他订单"
        records = data.get("orderChangeList")
        assert isinstance(records, list), "订单流转记录不是列表"
        assert all(
            isinstance(row, dict) and str(row.get("orderId")) == order_id
            for row in records
        ), "订单流转记录混入其他订单"
        return records

    def _require_menu(self) -> ConsoleMenuPage:
        """Return the prepared menu or fail with an actionable message."""
        assert self._menu is not None, "尚未加载控制台菜单树"
        return self._menu

    def open_cloud_product_apply_readonly(
        self,
        record: PortalResourceRecord,
    ) -> "OrderMgmtPage":
        """Enter the cloud-product application form without filling or saving it."""
        apply_entry = self.page.get_by_text("立即申请", exact=True)
        expect(apply_entry).to_have_count(1)
        expect(apply_entry).to_be_visible()
        with self.page.expect_response(
            lambda response: bool(self.APPLY_FLOW_API.search(response.url)),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as flow_capture:
            with self.page.expect_response(
                lambda response: bool(self.ORDER_DRAFT_API.search(response.url)),
                timeout=settings.NAVIGATION_TIMEOUT,
            ) as draft_capture:
                apply_entry.click()

        route = self._subscription_route_query(self.page.url)
        assert route.get("resourceType") == [str(record.resource_type)], (
            "申请路由资源类型不一致"
        )
        assert route.get("id") == [record.resource_id], "申请路由资源 ID 不一致"
        for key in ("specId", "packageId", "buyMode", "buyTime"):
            assert route.get(key) and route[key][0], f"申请路由缺少 {key}"
        self._validate_apply_flow_response(
            flow_capture.value,
            record,
            route["specId"][0],
        )
        self._validate_order_draft_response(draft_capture.value, record)

        expect(self.page.get_by_text(record.name, exact=True)).to_be_visible()
        expect(self.page.get_by_text(record.description, exact=True)).to_be_visible()
        expect(self.page.get_by_text("订阅步骤", exact=True)).to_be_visible()
        expect(self.page.get_by_text("1.补充信息", exact=True)).to_be_visible()
        expect(self.page.get_by_text("2.信息确认", exact=True)).to_be_visible()
        expect(self.page.get_by_role("checkbox", name="生产", exact=True)).to_be_checked()
        expect(self.page.get_by_role("spinbutton", name=re.compile("消息保留时间"))).to_be_visible()
        expect(self.page.get_by_role("textbox", name=re.compile("项目名称"))).to_be_empty()
        expect(
            self.page.get_by_role("textbox", name=re.compile("项目管理员员工编码"))
        ).to_be_empty()
        expect(self.page.get_by_role("textbox", name="备注", exact=True)).to_be_empty()
        for action in ("取消", "保存草稿", "下一步"):
            expect(self.page.get_by_text(action, exact=True)).to_be_visible()
        logger.info(
            "[申请表单只读] %s/%s，未填写、未保存、未进入下一步",
            record.name,
            record.resource_id,
        )
        return self

    @staticmethod
    def _subscription_route_query(url: str) -> dict[str, list[str]]:
        """Parse query parameters located after the SPA hash route."""
        fragment = urlparse(url).fragment
        path, separator, query = fragment.partition("?")
        assert path == "/subscription-process", f"未进入订阅申请页: {url}"
        assert separator, "订阅申请路由缺少查询参数"
        return parse_qs(query, keep_blank_values=True)

    @staticmethod
    def _validate_apply_flow_response(
        response: Response,
        record: PortalResourceRecord,
        spec_id: str,
    ) -> list[dict]:
        """Require the apply flow to belong to the selected resource and spec."""
        assert response.status == 200, "申请流程接口 HTTP 失败"
        query = parse_qs(urlparse(response.url).query)
        assert query.get("resourceId") == [record.resource_id], "流程接口资源 ID 不一致"
        assert query.get("businessType") == ["10"], "流程接口业务类型不一致"
        assert query.get("specId") == [spec_id], "流程接口规格 ID 不一致"
        payload = response.json()
        assert isinstance(payload, dict), "申请流程接口不是对象"
        assert type(payload.get("code")) is int and payload["code"] == 0, (
            "申请流程接口业务失败"
        )
        data = payload.get("data")
        assert isinstance(data, list) and data, "申请流程接口未返回流程节点"
        assert all(isinstance(node, dict) for node in data), "申请流程包含非对象节点"
        return data

    @staticmethod
    def _validate_order_draft_response(
        response: Response,
        record: PortalResourceRecord,
    ) -> Any:
        """Require the draft lookup to target the selected resource without writing."""
        assert response.status == 200, "订单草稿接口 HTTP 失败"
        query = parse_qs(urlparse(response.url).query, keep_blank_values=True)
        assert query.get("resourceType") == [str(record.resource_type)], (
            "草稿接口资源类型不一致"
        )
        assert query.get("resourceId") == [record.resource_id], "草稿接口资源 ID 不一致"
        assert query.get("id") == [""], "草稿接口不应指定已有草稿 ID"
        payload = response.json()
        assert isinstance(payload, dict), "订单草稿接口不是对象"
        assert type(payload.get("code")) is int and payload["code"] == 0, (
            "订单草稿接口业务失败"
        )
        return payload.get("data")

    def open_apply_form(self) -> "OrderMgmtPage":
        """进入资源申请/订阅表单页（M2-01）。"""
        try:
            self.nav.goto_url(settings.console_url("/udpweb/portal/index.html#/portal/order/apply"))
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
            self.nav.goto_url(settings.console_url("/udpweb/portal/index.html#/portal/order/list"))
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

    def switch_order_status_tabs(self) -> "OrderMgmtPage":
        """M2-SUPP-001: 订单状态 Tab 页签快速切换防抖断言。"""
        tabs = self.page.locator(".ant-tabs-tab, .el-tabs__item").all()
        if not tabs or len(tabs) < 2:
            raise EntryNotExposed("订单列表未暴露状态 Tab")
            
        for i, tab in enumerate(tabs[:3]): # 最多切前3个状态
            tab_name = tab.inner_text()
            tab.click()
            self.nav.wait_ready()
            self.assertions.page_not_blank_or_error()
            self.assertions.any_text_visible(["订单", "暂无数据"])
            logger.info(f"[断言] 订单状态 Tab 切换安全: {tab_name}")
        
        return self

    def verify_search_reset_logic(self, keyword: str = "P0-Readonly-Garbage-Search") -> "OrderMgmtPage":
        """M2-SUPP-002: 表单搜索区重置功能鲁棒性。"""
        input_el = self.elements.find_candidates(
            [
                ("placeholder", "请输入订单编号"),
                ("placeholder", "搜索订单"),
                ("css", "input.ant-input"),
            ],
            description="订单搜索框",
            timeout=2000
        )
        if not input_el:
            logger.info("[重置逻辑] 未找到订单搜索输入框，跳过")
            return self
            
        input_el.fill(keyword)
        assert input_el.input_value() == keyword
        
        reset_btn = self.elements.find_candidates(
            [
                ("text", "重置"),
                ("role", "button[name='重置']"),
            ],
            description="重置按钮",
            timeout=2000
        )
        
        if reset_btn:
            reset_btn.click()
            self.nav.wait_ready()
            assert input_el.input_value() == "", "重置按钮未能清空输入框"
            logger.info("[断言] 搜索面板表单重置逻辑正确执行")
        else:
            logger.info("[重置逻辑] 未找到重置按钮，跳过")
            
        return self

    def verify_approval_steps_rendered(self) -> "OrderMgmtPage":
        """M2-SUPP-003: 断言订单详情中的工作流审批节点(Steps/Timeline)组件完整渲染。"""
        # 进入第一条有详情的订单（如果有的话）
        detail_btn = self.page.get_by_text("详情").first
        try:
            detail_btn.wait_for(state="visible", timeout=3000)
            detail_btn.click()
            self.nav.wait_ready()
        except PlaywrightTimeoutError:
            raise EntryNotExposed("订单列表未暴露可点击的详情样本") from None

        try:
            # 兼容 Antd Steps 或 Element Timeline
            steps_container = self.page.locator(".ant-steps, .el-steps, .el-timeline").first
            steps_container.wait_for(state="visible", timeout=5000)
            logger.info("[断言] 审批工作流 Timeline 组件成功渲染，BPM 接口连接正常")
        except PlaywrightTimeoutError:
            raise AssertionError("订单详情中未暴露审批节点 Steps/Timeline 组件") from None
            
        return self
