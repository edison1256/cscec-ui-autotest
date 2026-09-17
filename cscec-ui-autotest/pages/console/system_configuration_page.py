"""Read-only page object for console system-configuration pages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from playwright.sync_api import Page, Response, expect

from core.logger import get_logger
from pages.console.console_menu_page import ConsoleMenuPage


logger = get_logger("system_configuration_page")


@dataclass(frozen=True)
class SystemListRecord:
    """Display identity extracted from a system list response."""

    record_id: str
    display_name: str


class SystemConfigurationPage(ConsoleMenuPage):
    """Inspect portal configuration and audit logs without modifying them."""

    BANNER_API = "/banner/queryIrpBannerList"
    AUDIT_API = "/log-audit/page"

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self._record: SystemListRecord | None = None

    def open_homepage_configuration(self) -> "SystemConfigurationPage":
        """Open 首页配置 and validate a backend-provided banner identity."""
        self.open_console_home()
        response = self._open_authorized(
            ("系统配置", "门户管理", "首页配置"),
            self.BANNER_API,
            r"[#/]sub/resource/systemManage/portal/pageConfig(?:[/?]|$)",
        )
        self._record = self._record_from_response(
            response,
            "首页配置",
            id_fields=("id", "bannerId"),
            name_fields=("bannerName", "name", "title"),
        )
        expect(self.page.get_by_text("首页配置", exact=True).first).to_be_visible()
        expect(self.page.get_by_text(self._record.display_name, exact=True).first).to_be_visible()
        for label in ("PC端banner", "移动端banner"):
            expect(self.page.get_by_text(label, exact=True).first).to_be_visible()
        logger.info("[只读交互] 首页配置 Banner 身份正常: %s", self._record.display_name)
        return self

    def open_audit_log(self) -> "SystemConfigurationPage":
        """Open 日志审计查询 and validate one dynamic list identity."""
        self.open_console_home()
        response = self._open_authorized(
            ("系统配置", "日志审计查询"),
            self.AUDIT_API,
            r"[#/]sub/resource/systemManage/logAudit(?:[/?]|$)",
        )
        self._record = self._record_from_response(
            response,
            "日志审计",
            id_fields=("id", "logId", "requestId"),
            name_fields=("creatorName", "createName", "userName", "requestUri", "url"),
        )
        expect(self.page.get_by_role("button", name="查 询", exact=True)).to_be_visible()
        expect(self.page.get_by_role("button", name="重 置", exact=True)).to_be_visible()
        expect(self.page.get_by_text(self._record.record_id, exact=True).first).to_be_visible()
        logger.info("[只读交互] 日志审计列表身份正常: %s", self._record.record_id)
        return self

    def _open_authorized(
        self,
        titles: tuple[str, ...],
        api_pattern: str,
        route_pattern: str,
    ) -> Response:
        prerequisite = self.menu_path_prerequisite(*titles)
        assert prerequisite.satisfied, prerequisite.reason
        return self.open_menu_path(
            *titles,
            response_pattern=api_pattern,
            route_pattern=route_pattern,
        )

    @classmethod
    def _record_from_response(
        cls,
        response: Response,
        label: str,
        *,
        id_fields: tuple[str, ...],
        name_fields: tuple[str, ...],
    ) -> SystemListRecord:
        payload = cls._success_payload(response, label)
        rows = cls._records(payload.get("data"))
        assert rows and isinstance(rows[0], dict), f"{label}接口未返回有效记录"
        row = rows[0]
        return SystemListRecord(
            cls._required_field(row, *id_fields),
            cls._required_field(row, *name_fields),
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
        raise AssertionError(f"列表记录缺少字段: {'/'.join(names)}")
