"""Read-only page object for console system-configuration pages."""

from __future__ import annotations

from dataclasses import dataclass
import re
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
    CATEGORY_API = "/category/queryAllResourceLabel"
    SPECIFICATION_API = "/category-backend/queryCategoryTreeList"
    LAYER_API = "/data-system/dataCategoryList"
    MANUFACTURER_API = "/manufacturer/page"
    DEVELOPER_API = "/developer-platform-resource-portal/page"
    INSPECTION_API = "/irpTaskTpl/getIrpTaskTplList"
    WORK_ORDER_CONFIG_API = "/work-order-config/getCategory"

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

    def open_category_management(self) -> "SystemConfigurationPage":
        """Open 类目管理 and bind a resource-label identity."""
        return self._open_identity_page(
            ("系统配置", "资源配置", "类目管理"),
            self.CATEGORY_API,
            r"[#/]sub/resource/systemManage/label(?:[/?]|$)",
            "类目管理",
            id_fields=("id",),
            name_fields=("name",),
        )

    def open_specification_management(self) -> "SystemConfigurationPage":
        """Open 规格管理 and bind a backend-category identity."""
        return self._open_identity_page(
            ("系统配置", "资源配置", "规格管理"),
            self.SPECIFICATION_API,
            r"[#/]sub/resource/systemManage/specificationManage(?:[/?]|$)",
            "规格管理",
            id_fields=("id",),
            name_fields=("categoryName",),
        )

    def open_data_layer_settings(self) -> "SystemConfigurationPage":
        """Open 数据分层设置 and bind an application-domain identity."""
        return self._open_identity_page(
            ("系统配置", "资源配置", "数据分层设置"),
            self.LAYER_API,
            r"[#/]sub/resource/systemManage/layerSet(?:[/?]|$)",
            "数据分层设置",
            id_fields=("id",),
            name_fields=("name",),
        )

    def open_data_system_maintenance(self) -> "SystemConfigurationPage":
        """Require 数据系统维护 to remain on its declared route."""
        self.open_console_home()
        titles = ("系统配置", "资源配置", "数据系统维护")
        prerequisite = self.menu_path_prerequisite(*titles)
        assert prerequisite.satisfied, prerequisite.reason
        resolved = self._require_snapshot().path(*titles)
        assert resolved is not None
        for node in resolved[:-1]:
            item = self._menu_item(node.title)
            if item.get_attribute("aria-expanded") != "true":
                item.click()
                expect(item).to_have_attribute("aria-expanded", "true")
        self._menu_item(titles[-1]).click()
        expect(self.page).to_have_url(
            re.compile(r"[#/]sub/resource/systemManage/systemMaintain(?:[/?]|$)")
        )
        expect(
            self.page.get_by_text("数据系统维护", exact=True).last
        ).to_be_visible()
        self.assertions.page_not_blank_or_error()
        return self

    def open_manufacturer_management(self) -> "SystemConfigurationPage":
        """Open 厂商管理 and bind a manufacturer identity."""
        return self._open_identity_page(
            ("系统配置", "厂商管理"),
            self.MANUFACTURER_API,
            r"[#/]sub/resource/systemManage/manufacturerManage(?:[/?]|$)",
            "厂商管理",
            id_fields=("id",),
            name_fields=("manufacturerName",),
        )

    def open_developer_platform_configuration(self) -> "SystemConfigurationPage":
        """Open 开发者平台配置 and bind a displayed resource identity."""
        page = self._open_identity_page(
            ("系统配置", "门户管理", "开发者平台配置"),
            self.DEVELOPER_API,
            r"[#/]sub/resource/systemManage/portal/developerConfig(?:[/?]|$)",
            "开发者平台配置",
            id_fields=("id",),
            name_fields=("name",),
        )
        for action in ("新 增", "上移", "下移", "删除"):
            expect(self.page.get_by_role("button", name=action, exact=True).first).to_be_visible()
        return page

    def open_inspection_configuration(self) -> "SystemConfigurationPage":
        """Open 巡检配置 and bind a manual-inspection template identity."""
        page = self._open_identity_page(
            ("系统配置", "巡检配置"),
            self.INSPECTION_API,
            r"[#/]sub/resource/systemManage/inspectionConfig(?:[/?]|$)",
            "巡检配置",
            id_fields=("id",),
            name_fields=("taskName",),
        )
        for tab in ("人工巡检", "自动巡检"):
            expect(self.page.get_by_text(tab, exact=True).first).to_be_visible()
        for action in ("新 增", "编辑", "删除", "编辑模版"):
            expect(self.page.get_by_role("button", name=action, exact=True).first).to_be_visible()
        return page

    def open_work_order_configuration(self) -> "SystemConfigurationPage":
        """Open 工单配置 and bind a root category identity."""
        page = self._open_identity_page(
            ("系统配置", "工单配置"),
            self.WORK_ORDER_CONFIG_API,
            r"[#/]sub/resource/systemManage/workOrderConfig(?:[/?]|$)",
            "工单配置",
            id_fields=("categoryCode", "libraryCode", "key"),
            name_fields=("categoryName", "libraryName", "title"),
        )
        for action in ("修改分类", "全局处理人"):
            expect(self.page.get_by_role("button", name=action, exact=True)).to_be_visible()
        expect(self.page.get_by_text("工单类型", exact=True)).to_be_visible()
        return page

    def _open_identity_page(
        self,
        titles: tuple[str, ...],
        api_pattern: str,
        route_pattern: str,
        label: str,
        *,
        id_fields: tuple[str, ...],
        name_fields: tuple[str, ...],
    ) -> "SystemConfigurationPage":
        self.open_console_home()
        response = self._open_authorized(titles, api_pattern, route_pattern)
        self._record = self._record_from_response(
            response,
            label,
            id_fields=id_fields,
            name_fields=name_fields,
        )
        expect(self.page.get_by_text(label, exact=True).first).to_be_visible()
        expect(
            self.page.get_by_text(self._record.display_name, exact=True).first
        ).to_be_visible()
        logger.info("[只读交互] %s列表身份正常: %s", label, self._record.record_id)
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
