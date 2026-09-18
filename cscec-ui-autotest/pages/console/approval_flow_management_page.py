"""Read-only page object for approval flow management and monitoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from playwright.sync_api import Page, Response, expect

from core.logger import get_logger
from pages.console.console_menu_page import ConsoleMenuPage


logger = get_logger("approval_flow_management_page")


@dataclass(frozen=True)
class FlowTemplateRecord:
    """Identity of one configured approval flow template."""

    template_id: str
    name: str
    creator_name: str


@dataclass(frozen=True)
class FlowMonitorRecord:
    """Identity of one monitored approval process instance."""

    process_instance_id: str
    definition_code: str
    description: str
    status_name: str


class ApprovalFlowManagementPage(ConsoleMenuPage):
    """Inspect approval flow configuration and runtime history without writes."""

    TEMPLATE_API = "/irp-api/irp-portal-console/flow-template/page"
    MONITOR_API = "/workflow/process/getProcessedMonitor"
    TASK_HISTORY_API = "/workflow/task/getTasksByProcInst"
    COMMENT_TREE_API = "/workflow/process/getProcessCommentTree"

    def __init__(self, page: Page) -> None:
        super().__init__(page)

    def inspect_flow_management_list(self) -> "ApprovalFlowManagementPage":
        """Validate the flow-management list and its first dynamic identity."""
        self.open_console_home()
        titles = ("审批流程", "流程管理")
        prerequisite = self.menu_path_prerequisite(*titles)
        assert prerequisite.satisfied, prerequisite.reason
        response = self.open_menu_path(
            *titles,
            response_pattern=self.TEMPLATE_API,
            route_pattern=r"[#/]sub/resource/systemManage/processManage(?:[/?]|$)",
        )
        record = self._template_record(response)
        expect(self.page.get_by_role("button", name="查 询", exact=True)).to_be_visible()
        expect(self.page.get_by_role("button", name="重 置", exact=True)).to_be_visible()
        expect(self.page.get_by_role("button", name="新建流程", exact=True)).to_be_visible()
        row = self.page.get_by_text(record.name, exact=True).first.locator(
            "xpath=ancestor::div[contains(@class,'table-row')][1]"
        )
        expect(row).to_contain_text(record.creator_name)
        for action in ("进入流程画布", "配置表单", "更多"):
            expect(row.get_by_text(action, exact=True)).to_be_visible()
        logger.info(
            "[只读交互] 流程管理动态身份正常: %s/%s",
            record.template_id,
            record.name,
        )
        return self

    def inspect_flow_monitor_history(self) -> "ApprovalFlowManagementPage":
        """Open the first process history drawer without invoking task actions."""
        self.open_console_home()
        titles = ("审批流程", "流程监控")
        prerequisite = self.menu_path_prerequisite(*titles)
        assert prerequisite.satisfied, prerequisite.reason
        response = self.open_menu_path(
            *titles,
            response_pattern=self.MONITOR_API,
            route_pattern=r"[#/]sub/workflow/flowwatch(?:[/?]|$)",
        )
        record = self._monitor_record(response)
        expect(self.page.get_by_role("button", name="查 询", exact=True)).to_be_visible()
        expect(self.page.get_by_role("button", name="重 置", exact=True)).to_be_visible()
        expect(self.page.get_by_role("button", name="导 出", exact=True)).to_be_visible()
        row = self.page.get_by_text(
            record.process_instance_id,
            exact=True,
        ).first.locator("xpath=ancestor::div[contains(@class,'table-row')][1]")
        for identity in (
            record.definition_code,
            record.description,
            record.status_name,
        ):
            expect(row).to_contain_text(identity)

        with self.page.expect_response(
            lambda item: self.TASK_HISTORY_API in item.url,
        ) as task_response:
            with self.page.expect_response(
                lambda item: self.COMMENT_TREE_API in item.url,
            ) as comment_response:
                self.page.get_by_text(
                    record.process_instance_id,
                    exact=True,
                ).first.click()
        self._assert_success(task_response.value, "流程任务历史")
        self._assert_success(comment_response.value, "流程评论树")
        history_panel = self.page.get_by_role("tabpanel", name="流程监控")
        expect(history_panel.get_by_text("待办任务", exact=True)).to_be_visible()
        expect(history_panel.get_by_text("办理历史", exact=True)).to_be_visible()
        expect(history_panel.get_by_text("任务号", exact=True)).to_be_visible()
        expect(history_panel.get_by_text("节点名称", exact=True)).to_be_visible()
        for risky_action in ("转签", "加签", "驳回", "跳过"):
            expect(
                history_panel.get_by_text(risky_action, exact=True).first
            ).to_be_visible()
        logger.info(
            "[只读详情] 流程监控历史正常: %s/%s",
            record.process_instance_id,
            record.definition_code,
        )
        return self

    @classmethod
    def _template_record(cls, response: Response) -> FlowTemplateRecord:
        rows = cls._successful_rows(response, "流程管理")
        row = rows[0]
        return FlowTemplateRecord(
            template_id=cls._required_field(row, "id"),
            name=cls._required_field(row, "name"),
            creator_name=cls._required_field(row, "creatorName"),
        )

    @classmethod
    def _monitor_record(cls, response: Response) -> FlowMonitorRecord:
        rows = cls._successful_rows(response, "流程监控")
        row = rows[0]
        return FlowMonitorRecord(
            process_instance_id=cls._required_field(row, "procInstId"),
            definition_code=cls._required_field(row, "modelId", "procDefId"),
            description=cls._required_field(row, "description"),
            status_name=cls._required_field(row, "statusName"),
        )

    @classmethod
    def _successful_rows(
        cls,
        response: Response,
        label: str,
    ) -> list[dict[str, Any]]:
        cls._assert_success(response, label)
        payload = response.json()
        data = payload.get("data")
        rows = data.get("list") if isinstance(data, dict) else None
        assert isinstance(rows, list) and rows and isinstance(rows[0], dict), (
            f"{label}接口未返回有效记录"
        )
        return rows

    @staticmethod
    def _assert_success(response: Response, label: str) -> None:
        assert response.status == 200, f"{label}接口 HTTP 失败: {response.status}"
        payload = response.json()
        assert isinstance(payload, dict), f"{label}接口响应不是对象"
        assert payload.get("code") in (0, 200, "0", "200"), (
            f"{label}接口业务失败: {payload.get('code')}/{payload.get('message')}"
        )

    @staticmethod
    def _required_field(row: dict[str, Any], *names: str) -> str:
        for name in names:
            value = row.get(name)
            if value is not None and str(value).strip():
                return str(value).strip()
        raise AssertionError(f"审批流程记录缺少字段: {'/'.join(names)}")
