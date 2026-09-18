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


@dataclass(frozen=True)
class EvaluationRecord:
    """Identity fields for one submitted evaluation."""

    evaluation_id: str
    creator_name: str
    object_name: str
    score: str


class EvaluationManagementPage(ConsoleMenuPage):
    """Inspect evaluation templates without invoking write actions."""

    LIST_API = "/assessment-template/page"
    EVALUATION_LIST_API = "/assessment/page"

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

    def inspect_first_evaluation_detail(self) -> "EvaluationManagementPage":
        """Query one template's evaluations and open the first read-only detail."""
        self.open()
        template = self._require_record()
        template_row = self.page.get_by_text(
            template.name,
            exact=True,
        ).filter(visible=True).first.locator(
            "xpath=ancestor::div[contains(@class,'table-row')][1]"
        )
        template_row.get_by_text("查看评价", exact=True).click()
        drawer = self.page.locator(
            ".ant-drawer:visible, .el-drawer:visible"
        ).first
        expect(drawer.get_by_text("评价数据", exact=True)).to_be_visible()

        with self.page.expect_response(
            lambda response: self.EVALUATION_LIST_API in response.url,
        ) as response_info:
            drawer.get_by_role("button", name="查 询", exact=True).click()
        evaluation = self._evaluation_from_response(response_info.value)

        row = drawer.get_by_text(
            evaluation.creator_name,
            exact=True,
        ).first.locator(
            "xpath=ancestor::div[contains(@class,'table-row')][1]"
        )
        for identity in (
            evaluation.creator_name,
            evaluation.object_name,
            evaluation.score,
        ):
            expect(row).to_contain_text(identity)
        row.get_by_text("详情", exact=True).click()

        detail = self.page.locator(".ant-modal:visible").last
        expect(detail.get_by_text("评价详情", exact=True)).to_be_visible()
        for label in (
            "评价人姓名",
            "评价人编号",
            "评价时间",
            "评价人部门",
            "评价对象ID",
            "评价综合得分",
            "评价综合星级",
            "评价对象",
        ):
            expect(detail.get_by_text(label, exact=True)).to_be_visible()
        expect(detail.get_by_role("button", name="关 闭", exact=True)).to_be_visible()
        logger.info(
            "[只读详情] 评价数据: id=%s, creator=%s, object=%s",
            evaluation.evaluation_id,
            evaluation.creator_name,
            evaluation.object_name,
        )
        return self

    def _require_record(self) -> EvaluationTemplateRecord:
        assert self._record is not None, "尚未绑定评价模板记录"
        return self._record

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

    @classmethod
    def _evaluation_from_response(cls, response: Response) -> EvaluationRecord:
        payload = cls._success_payload(response, "评价数据列表")
        rows = cls._records(payload.get("data"))
        assert rows and isinstance(rows[0], dict), "评价数据列表未返回有效记录"
        row = rows[0]
        score = row.get("comprehensiveScore")
        assert isinstance(score, (int, float)), "评价数据缺少有效综合得分"
        return EvaluationRecord(
            evaluation_id=cls._required_field(row, "id"),
            creator_name=cls._required_field(row, "creatorName"),
            object_name=cls._required_field(row, "evaluationObjectName"),
            score=f"{score:g}",
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
