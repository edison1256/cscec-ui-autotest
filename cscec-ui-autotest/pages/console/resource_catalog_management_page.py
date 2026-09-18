"""Read-only page object for resource-catalog management leaves."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from playwright.sync_api import Locator, Page, Request, Response, expect

from config.settings import settings
from core.interaction_evidence import click_and_expect, require_actionable
from pages.console.console_menu_page import ConsoleMenuPage


@dataclass(frozen=True)
class CatalogRecord:
    """One resource identity returned by a catalog list endpoint."""

    record_id: str
    name: str
    code: str


class ResourceCatalogManagementPage(ConsoleMenuPage):
    """Inspect resource-management lists without changing production data."""

    APPLICATION_LIST_API = "/app-list/console-list"
    APPLICATION_DETAIL_API = "/app/detail"
    CLOUD_LIST_API = "/cloud/list"
    API_APPLICATION_LIST_API = "/app/list-businessArea-app"
    DATA_ASSET_LIST_API = "/data-property/tableList"
    SOLUTION_LIST_API = "/solution/page"
    PROD_APPLICATION_SAMPLE = "0512prodtest"
    PROD_CLOUD_SAMPLE = "金仓数据库_测试专用"

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self.record: CatalogRecord | None = None

    def inspect_application_list_and_detail(self) -> "ResourceCatalogManagementPage":
        """Bind the first application list identity to its exact detail response."""
        response = self._open_list_page(
            "应用管理",
            self.APPLICATION_LIST_API,
            r"[#/]resource/appInfo/appList(?:[/?]|$)",
        )
        self.record = self._record_from_response(
            response,
            label="应用管理",
            name_fields=("appName",),
            code_fields=("productCode", "appCode", "code"),
        )
        row = self._record_row(self.record.name)
        expect(row).to_contain_text(self.record.name)

        detail_action = row.get_by_text("详情", exact=True)
        require_actionable(detail_action, f"查看应用详情 {self.record.name}")
        with self.page.expect_response(
            lambda result: (
                self.APPLICATION_DETAIL_API in result.url
                and f"id={self.record.record_id}" in result.url
            ),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as detail_info:
            click_and_expect(
                detail_action,
                lambda: expect(
                    self.page.get_by_text("应用注册详情", exact=True)
                ).to_be_visible(),
                action_name=f"查看应用详情 {self.record.name}",
            )
        self._assert_detail_identity(detail_info.value, self.record, "应用详情")
        expect(self.page.get_by_text("基础信息", exact=True).last).to_be_visible()
        expect(self.page.get_by_text("联系人信息", exact=True).last).to_be_visible()
        expect(self.page.get_by_role("button", name="关 闭", exact=True)).to_be_visible()
        return self

    def inspect_cloud_product_list_and_detail(self) -> "ResourceCatalogManagementPage":
        """Open one exact cloud-product row and verify its read-only dialog."""
        response = self._open_list_page(
            "云产品管理",
            self.CLOUD_LIST_API,
            r"[#/]resource/cloud(?:[/?]|$)",
        )
        self.record = self._record_from_response(
            response,
            label="云产品管理",
            name_fields=("name",),
            code_fields=("resourceCode", "code"),
        )
        row = self._record_row(self.record.name)
        expect(row).to_contain_text(self.record.name)
        expect(row).to_contain_text(self.record.code)

        detail_action = row.get_by_text("详情", exact=True)
        click_and_expect(
            detail_action,
            lambda: expect(self.page.get_by_text("查看", exact=True).last).to_be_visible(),
            action_name=f"查看云产品详情 {self.record.name}",
        )
        for tab in ("基本信息", "联系人信息", "上架信息", "4A信息"):
            expect(self.page.get_by_text(tab, exact=True).last).to_be_visible()
        expect(self.page.get_by_role("button", name="取 消", exact=True)).to_be_visible()
        return self

    def inspect_api_management_shell(self) -> "ResourceCatalogManagementPage":
        """Verify the API page's application source and selection control."""
        self.open_console_home()
        titles = ("资源管理", "API管理")
        prerequisite = self.menu_path_prerequisite(*titles)
        assert prerequisite.satisfied, prerequisite.reason
        response = self.open_menu_path(
            *titles,
            response_pattern=self.API_APPLICATION_LIST_API,
            route_pattern=r"[#/]resource/apiResource(?:[/?]|$)",
        )
        payload = self._success_payload(response, "API管理应用列表")
        assert isinstance(payload.get("data"), list), "API管理应用列表 data 不是列表"
        label = self.page.get_by_text("选择应用：", exact=True).filter(visible=True)
        expect(label).to_be_visible()
        select = label.locator("xpath=..").locator(".ant-select")
        expect(select).to_be_visible()
        return self

    def inspect_component_management_shell(self) -> "ResourceCatalogManagementPage":
        """Verify the currently exposed component-management route and title."""
        self.open_console_home()
        titles = ("资源管理", "组件管理")
        prerequisite = self.menu_path_prerequisite(*titles)
        assert prerequisite.satisfied, prerequisite.reason
        self.open_menu_route(
            *titles,
            route_pattern=r"[#/]resource/comp(?:[/?]|$)",
        )
        expect(self.page.get_by_text("组件管理", exact=True).filter(visible=True).last).to_be_visible()
        return self

    def inspect_data_asset_list_and_detail(self) -> "ResourceCatalogManagementPage":
        """Open an exact data-asset row and verify its metadata detail tabs."""
        response = self._open_list_page(
            "数据资产管理",
            self.DATA_ASSET_LIST_API,
            r"[#/]resource/data(?:[/?]|$)",
        )
        self.record = self._record_from_response(
            response,
            label="数据资产管理",
            name_fields=("name",),
            code_fields=("propertyCode",),
        )
        row = self._record_row(self.record.name)
        expect(row).to_contain_text(self.record.name)
        expect(row).to_contain_text(self.record.code)
        click_and_expect(
            row.get_by_text("详情", exact=True),
            lambda: expect(
                self.page.get_by_text("技术元数据", exact=True).last
            ).to_be_visible(),
            action_name=f"查看数据资产详情 {self.record.name}",
        )
        for tab in ("技术元数据", "业务元数据", "管理元数据"):
            expect(self.page.get_by_text(tab, exact=True).last).to_be_visible()
        expect(self.page.get_by_role("button", name="返 回", exact=True)).to_be_visible()
        return self

    def inspect_solution_list_and_detail(self) -> "ResourceCatalogManagementPage":
        """Open an exact solution row and verify its read-only detail fields."""
        response = self._open_list_page(
            "解决方案管理",
            self.SOLUTION_LIST_API,
            r"[#/]resource/solution(?:[/?]|$)",
        )
        self.record = self._record_from_response(
            response,
            label="解决方案管理",
            name_fields=("name",),
            code_fields=("code",),
        )
        row = self._record_row(self.record.name)
        expect(row).to_contain_text(self.record.name)
        expect(row).to_contain_text(self.record.code)
        click_and_expect(
            row.get_by_text("详情", exact=True),
            lambda: expect(
                self.page.get_by_text("正文内容", exact=True).last
            ).to_be_visible(),
            action_name=f"查看解决方案详情 {self.record.name}",
        )
        for label in ("基础信息", "联系人信息", "热门推荐图片", "方案名称"):
            expect(self.page.get_by_text(label, exact=True).last).to_be_visible()
        return self

    def inspect_hardware_management_shell(self) -> "ResourceCatalogManagementPage":
        """Verify the currently exposed hardware-management route and title."""
        self.open_console_home()
        titles = ("资源管理", "硬件管理")
        prerequisite = self.menu_path_prerequisite(*titles)
        assert prerequisite.satisfied, prerequisite.reason
        self.open_menu_route(
            *titles,
            route_pattern=r"[#/]resource/hardware(?:[/?]|$)",
        )
        expect(self.page.get_by_text("硬件管理", exact=True).filter(visible=True).last).to_be_visible()
        return self

    def inspect_prod_application_unpublish_confirmation(
        self,
    ) -> "ResourceCatalogManagementPage":
        """Open and cancel unpublish confirmation for the dedicated prod app."""
        row = self._search_exact_record(
            title="应用管理",
            api_pattern=self.APPLICATION_LIST_API,
            route_pattern=r"[#/]resource/appInfo/appList(?:[/?]|$)",
            placeholder="请输入应用名称",
            name=self.PROD_APPLICATION_SAMPLE,
        )
        self._open_and_cancel_confirmation(
            row.get_by_text("下架", exact=True),
            expected_text="确定下架该应用吗？",
            action_name=f"下架应用 {self.PROD_APPLICATION_SAMPLE}",
        )
        return self

    def inspect_prod_cloud_delete_confirmation(
        self,
    ) -> "ResourceCatalogManagementPage":
        """Open and cancel delete confirmation for the dedicated prod cloud item."""
        row = self._search_exact_record(
            title="云产品管理",
            api_pattern=self.CLOUD_LIST_API,
            route_pattern=r"[#/]resource/cloud(?:[/?]|$)",
            placeholder="请输入名称",
            name=self.PROD_CLOUD_SAMPLE,
        )
        more = row.get_by_text("更多", exact=True)
        require_actionable(more, f"展开云产品操作 {self.PROD_CLOUD_SAMPLE}")
        more.hover()
        dropdown = self.page.locator(".ant-dropdown:visible").last
        expect(dropdown).to_be_visible()
        self._open_and_cancel_confirmation(
            dropdown.get_by_text("删除", exact=True),
            expected_text="是否确认删除该云资源，删除后将不可恢复？",
            action_name=f"删除云产品 {self.PROD_CLOUD_SAMPLE}",
        )
        return self

    def _open_list_page(
        self,
        title: str,
        api_pattern: str,
        route_pattern: str,
    ) -> Response:
        self.open_console_home()
        titles = ("资源管理", title)
        prerequisite = self.menu_path_prerequisite(*titles)
        assert prerequisite.satisfied, prerequisite.reason
        return self.open_menu_path(
            *titles,
            response_pattern=api_pattern,
            route_pattern=route_pattern,
        )

    def _search_exact_record(
        self,
        *,
        title: str,
        api_pattern: str,
        route_pattern: str,
        placeholder: str,
        name: str,
    ) -> Locator:
        self._open_list_page(title, api_pattern, route_pattern)
        search = self.page.get_by_placeholder(placeholder, exact=True)
        expect(search).to_be_visible()
        search.fill(name)
        with self.page.expect_response(
            lambda response: api_pattern in response.url,
            timeout=settings.NAVIGATION_TIMEOUT,
        ):
            self.page.get_by_role("button", name="查 询", exact=True).click()
        row = self._record_row(name)
        expect(row).to_contain_text(name)
        return row

    def _open_and_cancel_confirmation(
        self,
        action: Locator,
        *,
        expected_text: str,
        action_name: str,
    ) -> None:
        require_actionable(action, action_name)
        non_get_requests: list[str] = []

        def record_non_get(request: Request) -> None:
            if request.method.upper() != "GET":
                non_get_requests.append(f"{request.method} {request.url}")

        self.page.on("request", record_non_get)
        try:
            action.click()
            dialog = self.page.get_by_role("dialog").filter(has_text=expected_text)
            expect(dialog).to_be_visible()
            cancel = dialog.get_by_role("button", name="取 消", exact=True)
            require_actionable(cancel, f"取消{action_name}")
            cancel.click()
            expect(dialog).to_be_hidden()
        finally:
            self.page.remove_listener("request", record_non_get)
        assert not non_get_requests, (
            f"{action_name}在最终确认前产生了非 GET 请求: {non_get_requests}"
        )

    def _record_row(self, name: str):
        cell = self.page.get_by_text(name, exact=True).filter(visible=True).first
        expect(cell).to_be_visible()
        return cell.locator(
            "xpath=ancestor::div["
            "contains(concat(' ', normalize-space(@class), ' '), ' table-row ')][1]"
        )

    @classmethod
    def _record_from_response(
        cls,
        response: Response,
        *,
        label: str,
        name_fields: tuple[str, ...],
        code_fields: tuple[str, ...],
    ) -> CatalogRecord:
        payload = cls._success_payload(response, label)
        rows = cls._records(payload.get("data"))
        assert rows and isinstance(rows[0], dict), f"{label}接口未返回有效记录"
        row = rows[0]
        return CatalogRecord(
            record_id=cls._required_field(row, "id"),
            name=cls._required_field(row, *name_fields),
            code=cls._required_field(row, *code_fields),
        )

    @classmethod
    def _assert_detail_identity(
        cls,
        response: Response,
        record: CatalogRecord,
        label: str,
    ) -> None:
        payload = cls._success_payload(response, label)
        data = payload.get("data")
        assert isinstance(data, dict), f"{label} data 不是对象"
        assert cls._required_field(data, "id") == record.record_id, (
            f"{label}返回了其他业务对象"
        )
        assert cls._required_field(data, "appName", "name") == record.name, (
            f"{label}名称与列表不一致"
        )

    @staticmethod
    def _success_payload(response: Response, label: str) -> dict[str, Any]:
        assert response.status == 200, f"{label}接口 HTTP 失败: {response.status}"
        payload = response.json()
        assert isinstance(payload, dict), f"{label}接口响应不是对象"
        assert payload.get("code") in (0, 200, "0", "200"), (
            f"{label}接口业务失败: {payload.get('code')}/{payload.get('message')}"
        )
        return payload

    @staticmethod
    def _records(data: Any) -> list[Any]:
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            for key in ("records", "list", "rows", "content"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
        return []

    @staticmethod
    def _required_field(row: dict[str, Any], *names: str) -> str:
        for name in names:
            value = row.get(name)
            if value is not None and str(value).strip():
                return str(value).strip()
        raise AssertionError(f"记录缺少字段: {'/'.join(names)}")
