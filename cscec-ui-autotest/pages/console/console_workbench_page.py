"""Strict console workbench module-entry interactions."""

from __future__ import annotations

from dataclasses import dataclass
import re
from urllib.parse import urlparse

from playwright.sync_api import Page, Response, expect

from config.settings import settings
from core.base_page import BasePage
from core.execution_contract import PrerequisiteResult
from core.interaction_evidence import click_and_expect, require_actionable
from core.logger import get_logger


logger = get_logger("console_workbench_page")


@dataclass(frozen=True)
class WorkbenchSnapshot:
    """Effective workbench module configuration visible to the current account."""

    module_labels: tuple[str, ...]
    backend_function_count: int


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
    def _console_host() -> str:
        return urlparse(settings.CONSOLE_BASE_URL).netloc.lower()
