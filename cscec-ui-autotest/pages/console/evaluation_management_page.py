"""Read-only page object for evaluation data management."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from playwright.sync_api import Page, Response, expect

from core.logger import get_logger
from pages.console.console_menu_page import ConsoleMenuPage


logger = get_logger("evaluation_management_page")


@dataclass(frozen=True)
class EvaluationTemplateRecord:
    """Stable identity for one evaluation template row."""

    template_id: str
    name: str


class EvaluationManagementPage(ConsoleMenuPage):
    """Inspect evaluation templates without invoking write actions."""

    LIST_API = "/assessment-template/page"

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self._record: EvaluationTemplateRecord | None = None

    def open(self) -> "EvaluationManagementPage":
        """Open the authorized evaluation list and bind its first identity."""
        self.open_console_home()
        prerequisite = self.menu_path_prerequisite("评价中心", "评价数据管理")
        assert prerequisite.satisfied, prerequisite.reason
        response = self.open_menu_path(
            "评价中心",
            "评价数据管理",
            response_pattern=self.LIST_API,
            route_pattern=r"[#/]sub/resource/evaluateCenter/evaluateManage(?:[/?]|$)",
        )
        self._record = self._record_from_response(response)
        expect(self.page.get_by_text("评价数据管理", exact=True).first).to_be_visible()
        expect(self.page.get_by_text(self._record.name, exact=True).first).to_be_visible()
        expect(self.page.get_by_role("button", name="新建评价模板", exact=True)).to_be_visible()
        logger.info("[只读交互] 评价模板列表身份正常: %s", self._record.name)
        return self

    @classmethod
    def _record_from_response(cls, response: Response) -> EvaluationTemplateRecord:
        payload = cls._success_payload(response, "评价模板列表")
        rows = cls._records(payload.get("data"))
        assert rows and isinstance(rows[0], dict), "评价模板列表未返回有效记录"
        row = rows[0]
        return EvaluationTemplateRecord(
            cls._required_field(row, "id", "templateId"),
            cls._required_field(row, "assessmentName", "templateName", "name"),
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
                if isinstance(data.get(key), list):
                    return data[key]
        return []

    @staticmethod
    def _required_field(row: dict[str, Any], *names: str) -> str:
        for name in names:
            value = row.get(name)
            if value is not None and str(value).strip():
                return str(value).strip()
        raise AssertionError(f"评价模板记录缺少字段: {'/'.join(names)}")
