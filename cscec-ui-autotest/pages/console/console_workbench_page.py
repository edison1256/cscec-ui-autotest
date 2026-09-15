"""Strict console workbench module-entry interactions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Page, Response, expect

from config.settings import settings
from core.base_page import BasePage
from core.execution_contract import PrerequisiteResult
from core.interaction_evidence import (
    click_and_expect,
    require_actionable,
    require_business_identity,
)
from core.logger import get_logger


logger = get_logger("console_workbench_page")


@dataclass(frozen=True)
class WorkbenchSnapshot:
    """Effective workbench module configuration visible to the current account."""

    module_labels: tuple[str, ...]
    backend_function_count: int


@dataclass(frozen=True)
class WorkbenchListSnapshot:
    """Validated records returned by one workbench module list request."""

    module_label: str
    response_url: str
    records: tuple[Mapping[str, Any], ...]

    @property
    def first_record(self) -> Mapping[str, Any]:
        """Return the first record after its presence is declared applicable."""
        assert self.records, f"{self.module_label} 列表没有可用详情样本"
        return self.records[0]


class ConsoleWorkbenchPage(BasePage):
    """Open configured workbench cards and prove their target list surfaces."""

    WORKBENCH_ROUTE = (
        "/udpweb/portal/index.html#/portal/home/workbench?suitKey=portal"
    )
    COMMON_FUNCTIONS_PATTERN = re.compile(
        r"/irp-api/irp-portal-console/workbench/overview/commonfunctions/list"
    )

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self._snapshot: WorkbenchSnapshot | None = None

    def open(self) -> "ConsoleWorkbenchPage":
        """Open the actual workbench variant and capture its configuration response."""
        with self.page.expect_response(
            lambda response: bool(
                self.COMMON_FUNCTIONS_PATTERN.search(response.url)
            ),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as response_info:
            self.page.goto(
                settings.console_url(self.WORKBENCH_ROUTE),
                wait_until="domcontentloaded",
                timeout=settings.NAVIGATION_TIMEOUT,
            )

        function_count = self._validate_configuration_response(response_info.value)
        expect(self.page).to_have_url(
            re.compile(rf"^https?://{re.escape(self._console_host())}/")
        )
        expect(self.page.get_by_text("工作台", exact=True).first).to_be_visible()
        expect(self.page.get_by_text("常用模块", exact=True).first).to_be_visible()

        cards = self.page.locator(".moduleList .moduleItem")
        expect(cards.first).to_be_visible(timeout=settings.ACTION_TIMEOUT)
        labels = tuple(
            text.strip()
            for text in cards.locator(".itemLabel").all_inner_texts()
            if text.strip()
        )
        assert labels, "控制台工作台已加载但未渲染任何常用模块卡片"
        self._snapshot = WorkbenchSnapshot(labels, function_count)
        logger.info(
            "[前置条件] 工作台渲染 %s 个模块卡片，配置接口返回 %s 项",
            len(labels),
            function_count,
        )
        return self

    def module_prerequisite(self, label: str) -> PrerequisiteResult:
        """Describe whether the target card is in the effective workbench layout."""
        snapshot = self._require_snapshot()
        return PrerequisiteResult(
            satisfied=label in snapshot.module_labels,
            reason=f"当前工作台配置未展示模块卡片“{label}”",
            expected=f"常用模块包含“{label}”",
            actual=", ".join(snapshot.module_labels),
        )

    def open_module(
        self,
        label: str,
        expected_title: str,
        route_pattern: str,
    ) -> "ConsoleWorkbenchPage":
        """Click one exact card and require its route and business heading."""
        card = self.page.locator(".moduleList .moduleItem").filter(
            has=self.page.get_by_text(label, exact=True)
        ).first
        require_actionable(card, f"打开工作台模块 {label}")

        def destination_ready() -> None:
            expect(self.page).to_have_url(
                re.compile(route_pattern),
                timeout=settings.NAVIGATION_TIMEOUT,
            )
            heading = self.page.get_by_text(expected_title, exact=True).first
            expect(heading).to_be_visible(timeout=settings.NAVIGATION_TIMEOUT)

        click_and_expect(
            card,
            destination_ready,
            action_name=f"工作台模块 {label}",
        )
        self.assertions.page_not_blank_or_error()
        logger.info("[导航] 工作台模块 %s -> %s", label, expected_title)
        return self

    def open_module_with_list_snapshot(
        self,
        label: str,
        expected_title: str,
        route_pattern: str,
        list_api_pattern: str,
    ) -> WorkbenchListSnapshot:
        """Open one card and capture its API-backed list records."""
        api_pattern = re.compile(list_api_pattern)
        with self.page.expect_response(
            lambda response: bool(api_pattern.search(response.url)),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as response_info:
            self.open_module(label, expected_title, route_pattern)
        return self._parse_list_response(response_info.value, label)

    @staticmethod
    def detail_prerequisite(snapshot: WorkbenchListSnapshot) -> PrerequisiteResult:
        """Declare whether a list has a record that can be opened read-only."""
        return PrerequisiteResult(
            satisfied=bool(snapshot.records),
            reason=f"{snapshot.module_label} 当前没有可只读查看的详情样本",
            expected="列表接口至少返回 1 条记录",
            actual=f"records={len(snapshot.records)}",
        )

    def open_first_detail(
        self,
        snapshot: WorkbenchListSnapshot,
        *,
        row_identity_field: str,
        detail_identity_field: str,
        required_labels: Sequence[str],
        detail_api_pattern: str | None = None,
        visible_identity_field: str | None = None,
    ) -> "ConsoleWorkbenchPage":
        """Open the first API record's detail from its exact rendered row."""
        record = snapshot.first_record
        row_identity = self._required_record_text(record, row_identity_field)
        detail_identity = self._required_record_text(
            record,
            detail_identity_field,
        )
        expected_resource_name = self._record_resource_name(record)

        detail_button = self.page.get_by_role(
            "button",
            name="详情",
            exact=True,
        )
        row = self.page.locator(".table-row").filter(
            has=self.page.get_by_text(row_identity, exact=True)
        ).filter(has=detail_button).first
        require_business_identity(
            row,
            row_identity,
            f"{snapshot.module_label} 首条列表记录",
        )
        target = row.get_by_role("button", name="详情", exact=True)
        require_actionable(target, f"打开 {snapshot.module_label} 首条详情")

        overlay = self.page.locator(
            ".ant-drawer:visible, .ant-modal:visible, "
            ".el-dialog:visible, .el-drawer:visible"
        ).first

        def detail_ready() -> None:
            expect(overlay).to_be_visible(timeout=settings.NAVIGATION_TIMEOUT)
            for label in required_labels:
                expect(
                    overlay.get_by_text(label, exact=False).first
                ).to_be_visible(timeout=settings.ACTION_TIMEOUT)

        if detail_api_pattern:
            api_pattern = re.compile(detail_api_pattern)
            with self.page.expect_response(
                lambda response: self._response_matches_detail(
                    response,
                    api_pattern,
                    detail_identity,
                ),
                timeout=settings.NAVIGATION_TIMEOUT,
            ) as response_info:
                click_and_expect(
                    target,
                    detail_ready,
                    action_name=f"{snapshot.module_label} 首条详情",
                )
            self._validate_detail_response(
                response_info.value,
                detail_identity,
                expected_resource_name,
            )
        else:
            click_and_expect(
                target,
                detail_ready,
                action_name=f"{snapshot.module_label} 首条详情",
            )

        if visible_identity_field:
            visible_identity = self._required_record_text(
                record,
                visible_identity_field,
            )
            require_business_identity(
                overlay,
                visible_identity,
                f"{snapshot.module_label} 详情",
            )

        self.assertions.page_not_blank_or_error()
        logger.info(
            "[只读详情] %s: row=%s, detail=%s",
            snapshot.module_label,
            row_identity,
            detail_identity,
        )
        return self

    def _require_snapshot(self) -> WorkbenchSnapshot:
        assert self._snapshot is not None, "尚未捕获工作台模块配置"
        return self._snapshot

    @staticmethod
    def _validate_configuration_response(response: Response) -> int:
        assert response.status == 200, (
            f"工作台常用模块接口 HTTP 状态异常: {response.status} {response.url}"
        )
        payload = response.json()
        assert isinstance(payload, dict), "工作台常用模块接口响应不是 JSON 对象"
        code = payload.get("code")
        assert type(code) is int and code == 0, (
            f"工作台常用模块接口业务失败: code={code!r}, "
            f"message={payload.get('message')!r}"
        )
        data = payload.get("data")
        assert isinstance(data, list), "工作台常用模块接口 data 不是列表"
        return len(data)

    @staticmethod
    def _parse_list_response(
        response: Response,
        module_label: str,
    ) -> WorkbenchListSnapshot:
        assert response.status == 200, (
            f"{module_label} 列表接口 HTTP 状态异常: "
            f"{response.status} {response.url}"
        )
        payload = response.json()
        assert isinstance(payload, dict), f"{module_label} 列表接口响应不是 JSON 对象"
        code = payload.get("code")
        assert type(code) is int and code == 0, (
            f"{module_label} 列表接口业务失败: code={code!r}, "
            f"message={payload.get('message')!r}"
        )
        data = payload.get("data")
        assert isinstance(data, dict), f"{module_label} 列表接口 data 不是对象"
        records = data.get("list")
        assert isinstance(records, list), f"{module_label} 列表接口 data.list 不是列表"
        assert all(isinstance(record, dict) for record in records), (
            f"{module_label} 列表接口包含非对象记录"
        )
        return WorkbenchListSnapshot(
            module_label=module_label,
            response_url=response.url,
            records=tuple(records),
        )

    @staticmethod
    def _validate_detail_response(
        response: Response,
        expected_id: str,
        expected_resource_name: str,
    ) -> None:
        assert response.status == 200, (
            f"详情接口 HTTP 状态异常: {response.status} {response.url}"
        )
        payload = response.json()
        assert isinstance(payload, dict), "详情接口响应不是 JSON 对象"
        code = payload.get("code")
        assert type(code) is int and code == 0, (
            f"详情接口业务失败: code={code!r}, "
            f"message={payload.get('message')!r}"
        )
        data = payload.get("data")
        assert isinstance(data, dict), "详情接口 data 不是对象"
        actual_id = str(data.get("id") or "")
        assert actual_id == expected_id, (
            f"详情接口返回了错误业务对象: expected={expected_id!r}, "
            f"actual={actual_id!r}"
        )
        actual_resource_name = str(
            data.get("resourceName") or data.get("rscName") or ""
        )
        assert actual_resource_name == expected_resource_name, (
            "详情接口资源名与列表记录不一致: "
            f"expected={expected_resource_name!r}, "
            f"actual={actual_resource_name!r}"
        )

    @staticmethod
    def _response_matches_detail(
        response: Response,
        api_pattern: re.Pattern[str],
        expected_id: str,
    ) -> bool:
        if not api_pattern.search(response.url):
            return False
        query = parse_qs(urlparse(response.url).query)
        return query.get("id") == [expected_id]

    @staticmethod
    def _required_record_text(
        record: Mapping[str, Any],
        field: str,
    ) -> str:
        value = record.get(field)
        assert value is not None and str(value).strip(), (
            f"列表首条记录缺少有效字段 {field!r}: keys={sorted(record)}"
        )
        return str(value).strip()

    @staticmethod
    def _record_resource_name(record: Mapping[str, Any]) -> str:
        for field in ("resourceName", "rscName"):
            value = record.get(field)
            if value is not None and str(value).strip():
                return str(value).strip()
        raise AssertionError(
            f"列表首条记录缺少资源名称: keys={sorted(record)}"
        )

    @staticmethod
    def _console_host() -> str:
        return urlparse(settings.CONSOLE_BASE_URL).netloc.lower()
