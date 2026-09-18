"""Read-only page object for metering-statistics overview pages."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from playwright.sync_api import Page, Response, expect

from core.logger import get_logger
from pages.console.console_menu_page import ConsoleMenuPage


logger = get_logger("metering_statistics_page")


@dataclass(frozen=True)
class TenantOverviewRecord:
    """Tenant identity shown by a metering overview."""

    tenant_no: str
    tenant_name: str


class MeteringStatisticsPage(ConsoleMenuPage):
    """Inspect resource and subscription overviews without opening write flows."""

    RESOURCE_API = "/metrology/resource/overview/page"
    SUBSCRIPTION_API = "/metrology/tenant/apply/list"
    RESOURCE_DETAIL_API = "/metrology/resource/overview/view/tenant/detail"
    SUBSCRIPTION_DETAIL_API = "/metrology/tenant/apply/info"

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self._record: TenantOverviewRecord | None = None

    def open_resource_overview(self) -> "MeteringStatisticsPage":
        """Open 租户的资源/资源概览 and validate its first tenant."""
        return self._open_overview(
            ("计量统计", "租户的资源", "资源概览"),
            self.RESOURCE_API,
            r"[#/]sub/resource/measurement/resource(?:[/?]|$)",
            "资源概览",
        )

    def open_subscription_overview(self) -> "MeteringStatisticsPage":
        """Open 租户的订阅/订阅概览 and validate its first tenant."""
        return self._open_overview(
            ("计量统计", "租户的订阅", "订阅概览"),
            self.SUBSCRIPTION_API,
            r"[#/]sub/resource/measurement/subscription(?:[/?]|$)",
            "订阅概览",
        )

    def inspect_first_resource_tenant_detail(self) -> "MeteringStatisticsPage":
        """Open the first resource tenant's read-only metering detail."""
        self.open_resource_overview()
        record = self._require_record()
        with self.page.expect_response(
            lambda response: self.RESOURCE_DETAIL_API in response.url,
        ) as response_info:
            self._open_record_detail(record)
        self._assert_success(response_info.value, "租户资源详情")
        expect(self.page).to_have_url(
            re.compile(rf"/measurement/resource/tenant.*tenantNo={record.tenant_no}")
        )
        expect(
            self.page.get_by_text("租户的资源概览", exact=True)
            .filter(visible=True)
            .last
        ).to_be_visible()
        self._expect_tabs("云产品", "服务组件", "数据资产", "企业应用", "解决方案")
        expect(
            self.page.get_by_text("资源订阅详情", exact=True)
            .filter(visible=True)
            .last
        ).to_be_visible()
        logger.info("[只读详情] 租户资源详情正常: %s", record.tenant_no)
        return self

    def inspect_first_subscription_tenant_detail(self) -> "MeteringStatisticsPage":
        """Open the first subscription tenant's read-only metering detail."""
        self.open_subscription_overview()
        record = self._require_record()
        with self.page.expect_response(
            lambda response: self.SUBSCRIPTION_DETAIL_API in response.url,
        ) as response_info:
            self._open_record_detail(record)
        self._assert_success(response_info.value, "租户订阅详情")
        expect(self.page).to_have_url(
            re.compile(
                rf"/measurement/subscription/tenant.*tenantNo={record.tenant_no}"
            )
        )
        expect(
            self.page.get_by_text("租户的订阅概览", exact=True)
            .filter(visible=True)
            .last
        ).to_be_visible()
        self._expect_tabs("云产品", "服务组件", "数据资产", "企业应用")
        expect(
            self.page.get_by_text("资源订阅详情", exact=True)
            .filter(visible=True)
            .last
        ).to_be_visible()
        logger.info("[只读详情] 租户订阅详情正常: %s", record.tenant_no)
        return self

    def _open_record_detail(self, record: TenantOverviewRecord) -> None:
        row = self.page.get_by_text(record.tenant_no, exact=True).first.locator(
            "xpath=ancestor::div[contains(@class,'table-row')][1]"
        )
        expect(row).to_contain_text(record.tenant_name)
        row.get_by_role("button", name="查看", exact=True).click()

    def _expect_tabs(self, *names: str) -> None:
        for name in names:
            expect(self.page.get_by_role("tab", name=name, exact=True)).to_be_visible()

    def _require_record(self) -> TenantOverviewRecord:
        assert self._record is not None, "尚未绑定计量统计租户记录"
        return self._record

    def _open_overview(
        self,
        titles: tuple[str, ...],
        api_pattern: str,
        route_pattern: str,
        label: str,
    ) -> "MeteringStatisticsPage":
        self.open_console_home()
        prerequisite = self.menu_path_prerequisite(*titles)
        assert prerequisite.satisfied, prerequisite.reason
        response = self.open_menu_path(
            *titles,
            response_pattern=api_pattern,
            route_pattern=route_pattern,
        )
        self._record = self._record_from_response(response, label)
        expect(self.page.get_by_role("button", name="查 询", exact=True)).to_be_visible()
        expect(self.page.get_by_role("button", name="重 置", exact=True)).to_be_visible()
        expect(self.page.get_by_text(self._record.tenant_no, exact=True).first).to_be_visible()
        expect(self.page.get_by_text(self._record.tenant_name, exact=True).first).to_be_visible()
        logger.info("[只读交互] %s租户身份正常: %s", label, self._record.tenant_no)
        return self

    @classmethod
    def _record_from_response(
        cls, response: Response, label: str
    ) -> TenantOverviewRecord:
        assert response.status == 200, f"{label}接口 HTTP 失败: {response.status}"
        payload = response.json()
        assert isinstance(payload, dict), f"{label}接口响应不是对象"
        assert payload.get("code") in (0, 200, "0", "200"), (
            f"{label}接口业务失败: {payload.get('code')}/{payload.get('message')}"
        )
        rows = cls._records(payload.get("data"))
        assert rows and isinstance(rows[0], dict), f"{label}接口未返回有效记录"
        row = rows[0]
        return TenantOverviewRecord(
            cls._required_field(row, "tenantNo", "tenantCode"),
            cls._required_field(row, "tenantName", "orgName", "name"),
        )

    @staticmethod
    def _assert_success(response: Response, label: str) -> None:
        assert response.status == 200, f"{label}接口 HTTP 失败: {response.status}"
        payload = response.json()
        assert isinstance(payload, dict), f"{label}接口响应不是对象"
        assert payload.get("code") in (0, 200, "0", "200"), (
            f"{label}接口业务失败: {payload.get('code')}/{payload.get('message')}"
        )

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
        raise AssertionError(f"计量统计记录缺少字段: {'/'.join(names)}")
