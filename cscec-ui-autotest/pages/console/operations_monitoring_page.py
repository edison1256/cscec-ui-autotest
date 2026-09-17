"""Read-only page object for operations-monitoring console pages."""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from pages.console.console_menu_page import ConsoleMenuPage


class OperationsMonitoringPage(ConsoleMenuPage):
    """Open monitoring pages through their real nested menu paths."""

    def __init__(self, page: Page) -> None:
        super().__init__(page)

    def open_capacity_index(self) -> "OperationsMonitoringPage":
        """Open the capacity-index shell without invoking any write action."""
        return self._open_readonly_page(
            ("运维监控", "运维指标", "容量指标"),
            r"[#/]operationMaintenance/opsIndicator/capacityIndex(?:[/?]|$)",
            "容量指标",
        )

    def open_performance_index(self) -> "OperationsMonitoringPage":
        """Open performance metrics and verify its read-only query surface."""
        self._open_readonly_page(
            ("运维监控", "运维指标", "性能指标"),
            r"[#/]operationMaintenance/opsIndicator/performanceIndex(?:[/?]|$)",
            "性能指标",
        )
        expect(self.page.get_by_text("选择分类：", exact=True)).to_be_visible()
        expect(self.page.get_by_text("选择系统：", exact=True)).to_be_visible()
        expect(
            self.page.get_by_text("暂无数据", exact=True).filter(visible=True)
        ).to_be_visible()
        return self

    def open_polling(self) -> "OperationsMonitoringPage":
        """Open the inspection shell without starting an inspection."""
        self._open_readonly_page(
            ("运维监控", "运维巡检"),
            r"[#/]operationMaintenance/polling(?:[/?]|$)",
            "巡检概览",
        )
        for tab in ("巡检概览", "人工巡检", "自动巡检"):
            expect(self.page.get_by_text(tab, exact=True).last).to_be_visible()
        for metric in ("巡检任务数", "已完成巡检任务数", "异常巡检任务数", "异常任务占比"):
            expect(self.page.get_by_text(metric, exact=True)).to_be_visible()
        expect(self.page.locator("canvas").filter(visible=True).first).to_be_visible()
        return self

    def _open_readonly_page(
        self,
        titles: tuple[str, ...],
        route_pattern: str,
        heading: str,
    ) -> "OperationsMonitoringPage":
        self.open_console_home()
        prerequisite = self.menu_path_prerequisite(*titles)
        assert prerequisite.satisfied, prerequisite.reason
        self.open_menu_route(*titles, route_pattern=route_pattern)
        expect(self.page.get_by_text(heading, exact=True).last).to_be_visible()
        expect(self.page).to_have_url(re.compile(route_pattern))
        return self
