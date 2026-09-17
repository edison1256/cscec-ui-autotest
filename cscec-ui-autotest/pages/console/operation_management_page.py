"""Read-only page object for operation-management console pages."""

from __future__ import annotations

import re

from playwright.sync_api import Page, expect

from pages.console.console_menu_page import ConsoleMenuPage


class OperationManagementPage(ConsoleMenuPage):
    """Open operation-management pages without triggering business actions."""

    def __init__(self, page: Page) -> None:
        super().__init__(page)

    def open_operational_kanban(self) -> "OperationManagementPage":
        """Open the operational dashboard shell."""
        return self._open_readonly_page(
            ("运营管理", "运营报表", "运营看板"),
            r"[#/]operatingCenter/operatingStatement/operationalKanban(?:[/?]|$)",
            "运营看板",
        )

    def open_performance_insight(self) -> "OperationManagementPage":
        """Open the performance-insight shell."""
        return self._open_readonly_page(
            ("运营管理", "运营报表", "效能洞察"),
            r"[#/]operatingCenter/operatingStatement/performanceInsight(?:[/?]|$)",
            "效能洞察",
        )

    def open_group_dashboard(self) -> "OperationManagementPage":
        """Open the application-dashboard shell."""
        return self._open_readonly_page(
            ("运营管理", "运营报表", "应用看板"),
            r"[#/]operatingCenter/operatingStatement/groupDashboard(?:[/?]|$)",
            "应用看板",
        )

    def open_message_delivery(self) -> "OperationManagementPage":
        """Open message delivery without creating or sending a message."""
        return self._open_readonly_page(
            ("运营管理", "消息推送"),
            r"[#/]systemManage/sendMessage(?:[/?]|$)",
            "消息推送",
        )

    def _open_readonly_page(
        self,
        titles: tuple[str, ...],
        route_pattern: str,
        heading: str,
    ) -> "OperationManagementPage":
        self.open_console_home()
        prerequisite = self.menu_path_prerequisite(*titles)
        assert prerequisite.satisfied, prerequisite.reason
        self.open_menu_route(*titles, route_pattern=route_pattern)
        expect(self.page.get_by_text(heading, exact=True).last).to_be_visible()
        expect(self.page).to_have_url(re.compile(route_pattern))
        return self
