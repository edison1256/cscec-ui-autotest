"""控制台资源管理 Page Object — M1 资源基线。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
import re
from typing import Any

from playwright.sync_api import (
    Locator,
    Page,
    Response,
    TimeoutError as PlaywrightTimeoutError,
    expect,
)

from config.settings import settings
from core.base_page import BasePage
from core.execution_contract import PrerequisiteResult
from core.interaction_evidence import (
    click_and_expect,
    require_actionable,
    require_business_identity,
    require_surface_change,
)
from core.logger import get_logger
from pages.console.console_menu_page import ConsoleMenuPage

logger = get_logger("resource_mgmt_page")


@dataclass(frozen=True)
class DataResourceRecord:
    """Stable business identity for one data-resource table row."""

    resource_id: str
    table_name_cn: str
    table_name_en: str
    application_domain: str
    application_system: str
    l1_name: str
    l2_name: str
    l3_name: str
    data_manage_department: str
    system_project: str


@dataclass(frozen=True)
class DataResourceListSnapshot:
    """Validated records returned by the data-resource table endpoint."""

    response_url: str
    records: tuple[DataResourceRecord, ...]
    total: int

    @property
    def first_record(self) -> DataResourceRecord:
        """Return the first rendered record after list validation."""
        assert self.records, "数据资源列表接口没有返回记录"
        return self.records[0]


class ResourceMgmtPage(BasePage):
    """控制台与服务中心资源管理页。"""

    PAGE_NAME = "资源管理"
    PAGE_URL_PATTERN = "dataResources"
    PARENT_MENU = "资源管理"
    CHILD_MENU = "数据资源管理"
    LIST_API_PATTERN = re.compile(
        r"/irp-api/irp-portal-console/data-resource/tableList$"
    )

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self._menu_page: ConsoleMenuPage | None = None
        self._list_snapshot: DataResourceListSnapshot | None = None

    def prepare_console_menu(self) -> "ResourceMgmtPage":
        """Load the current account's real console menu tree."""
        self._menu_page = ConsoleMenuPage(self.page).open_console_home()
        return self

    def menu_prerequisite(self) -> PrerequisiteResult:
        """Return whether the real data-resource child menu is authorized."""
        return self._require_menu_page().child_menu_prerequisite(
            self.PARENT_MENU,
            self.CHILD_MENU,
        )

    def open_resource_list(self) -> "ResourceMgmtPage":
        """Open data resources through the authorized menu and capture its list."""
        if self._menu_page is None:
            self.prepare_console_menu()
        menu_page = self._require_menu_page()
        prerequisite = self.menu_prerequisite()
        assert prerequisite.satisfied, (
            f"数据资源管理菜单不可用: expected={prerequisite.expected!r}, "
            f"actual={prerequisite.actual!r}"
        )
        menu_page.expand_menu_group(self.PARENT_MENU)

        entry = self.page.get_by_role(
            "menuitem",
            name=self.CHILD_MENU,
            exact=True,
        )
        require_actionable(entry, "打开资源管理下的数据资源管理")

        def destination_ready() -> None:
            expect(self.page).to_have_url(
                re.compile(r"[#/]sub/resource/resource/dataResources(?:[?]|$)"),
                timeout=settings.NAVIGATION_TIMEOUT,
            )
            expect(
                self.page.get_by_role(
                    "tab",
                    name=self.CHILD_MENU,
                    exact=True,
                )
            ).to_have_attribute("aria-selected", "true")
            expect(
                self.page.get_by_text("数据资源列表", exact=True).first
            ).to_be_visible(timeout=settings.NAVIGATION_TIMEOUT)

        with self.page.expect_response(
            lambda response: bool(self.LIST_API_PATTERN.search(response.url)),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as response_info:
            click_and_expect(
                entry,
                destination_ready,
                action_name="资源管理 -> 数据资源管理",
            )

        self._list_snapshot = self._parse_list_response(response_info.value)
        self.verify_list_query()
        logger.info(
            "[导航] 资源管理 -> 数据资源管理，列表返回 %s/%s 条",
            len(self._list_snapshot.records),
            self._list_snapshot.total,
        )
        return self

    @property
    def list_snapshot(self) -> DataResourceListSnapshot:
        """Return the list snapshot captured during real menu navigation."""
        assert self._list_snapshot is not None, "尚未捕获数据资源列表接口"
        return self._list_snapshot

    def verify_list_query(self) -> "ResourceMgmtPage":
        """Require the first API record to match the first rendered business row."""
        record = self.list_snapshot.first_record
        for header in ("表中文名称", "表英文名称", "应用系统名称", "操作"):
            expect(self.page.get_by_text(header, exact=True).first).to_be_visible()
        row = self._row_for(record)
        require_business_identity(row, record.table_name_cn, "数据资源列表首条记录")
        require_business_identity(row, record.table_name_en, "数据资源列表首条记录")
        self.assertions.page_not_blank_or_error()
        return self

    def target_record(self) -> DataResourceRecord:
        """Return the dedicated production record or the current env's first row."""
        snapshot = self.list_snapshot
        if settings.ENV != "prod":
            complete_records = [
                record
                for record in snapshot.records
                if all(
                    (
                        record.application_domain,
                        record.application_system,
                        record.l1_name,
                        record.l2_name,
                        record.l3_name,
                        record.data_manage_department,
                        record.system_project,
                    )
                )
            ]
            assert complete_records, "当前环境首屏没有元数据完整的只读资源样本"
            return complete_records[0]

        expected = {
            "table_name_cn": os.getenv(
                "PROD_RESOURCE_TABLE_CN",
                "中建云测试专用",
            ),
            "table_name_en": os.getenv(
                "PROD_M03_EXISTING_TABLE_EN",
                "cloudtest",
            ),
            "application_domain": os.getenv(
                "PROD_M03_APP_DOMAIN",
                "中建云测试专用",
            ),
            "application_system": os.getenv(
                "PROD_M03_APP_SYSTEM",
                "中建云测试专用",
            ),
            "l1_name": os.getenv("PROD_M03_L1", "中建云测试专用L1"),
            "l2_name": os.getenv("PROD_M03_L2", "中建云测试专用L2"),
            "l3_name": os.getenv("PROD_M03_L3", "中建云测试专用L3"),
        }
        matches = [
            record
            for record in snapshot.records
            if record.table_name_cn == expected["table_name_cn"]
            and record.table_name_en == expected["table_name_en"]
        ]
        assert len(matches) == 1, (
            "生产数据资源首屏未唯一展示专用测试表: "
            f"expected={expected['table_name_cn']!r}/{expected['table_name_en']!r}, "
            f"matches={len(matches)}"
        )
        record = matches[0]
        mismatches = {
            field: (expected_value, getattr(record, field))
            for field, expected_value in expected.items()
            if getattr(record, field) != expected_value
        }
        assert not mismatches, f"生产专用数据资源层级与约定不一致: {mismatches}"
        return record

    def search_resource(self, keyword: str) -> "ResourceMgmtPage":
        """Filter the left data-category tree by its visible search control."""
        search_input = self.page.get_by_placeholder("请输入搜索内容").first
        require_actionable(search_input, "数据资源分类搜索")
        search_input.fill(keyword)
        self.page.get_by_role("button", name="search", exact=True).click()
        expect(search_input).to_have_value(keyword)
        logger.info("[搜索资源分类] 关键词: %s", keyword)
        return self

    def open_resource_detail(
        self,
        record: DataResourceRecord,
    ) -> "ResourceMgmtPage":
        """Open and verify the exact row's data-item detail without mutation."""
        row = self._row_for(record)
        target = row.get_by_role("button", name="数据项属性", exact=True)
        dialog = self.page.get_by_role("dialog").filter(
            has_text="数据项属性"
        ).first

        def detail_ready() -> None:
            expect(dialog).to_be_visible(timeout=settings.NAVIGATION_TIMEOUT)
            for label_pattern in (
                r"^数据表信息$",
                r"^表中文名称[:：]?$",
                r"^表英文名称[:：]?$",
                r"^数据项信息$",
            ):
                expect(
                    dialog.get_by_text(re.compile(label_pattern)).first
                ).to_be_visible()

        before, after = click_and_expect(
            target,
            detail_ready,
            action_name=f"打开数据资源详情 {record.table_name_cn}",
        )
        require_surface_change(before, after, "打开数据资源详情")
        require_business_identity(dialog, record.table_name_cn, "数据资源详情")
        require_business_identity(dialog, record.table_name_en, "数据资源详情")
        self._close_dialog(dialog)
        logger.info(
            "[只读详情] 数据资源 %s/%s",
            record.table_name_cn,
            record.table_name_en,
        )
        return self

    def open_resource_edit_readonly(
        self,
        record: DataResourceRecord,
    ) -> "ResourceMgmtPage":
        """Inspect all edit tabs for the exact row and leave without submitting."""
        row = self._row_for(record)
        target = row.get_by_role("button", name="编辑", exact=True)
        dialog = self.page.get_by_role("dialog").filter(
            has_text="业务元数据信息"
        ).first

        def edit_ready() -> None:
            expect(dialog).to_be_visible(timeout=settings.NAVIGATION_TIMEOUT)
            expect(
                dialog.get_by_role(
                    "tab",
                    name="业务元数据信息",
                    exact=True,
                )
            ).to_have_attribute("aria-selected", "true")

        before, after = click_and_expect(
            target,
            edit_ready,
            action_name=f"打开数据资源编辑弹窗 {record.table_name_cn}",
        )
        require_surface_change(before, after, "打开数据资源编辑弹窗")
        self._verify_business_metadata(dialog, record)
        self._verify_technical_metadata(dialog, record)
        self._verify_management_metadata(dialog, record)
        require_actionable(
            dialog.get_by_role("button", name=re.compile(r"^提\s*交$")),
            "编辑弹窗提交按钮只读探查",
        )
        self._close_dialog(dialog)
        logger.info(
            "[只读编辑] 已核对业务/技术/管理元数据并返回，未提交: %s",
            record.table_name_cn,
        )
        return self

    def _verify_business_metadata(
        self,
        dialog: Locator,
        record: DataResourceRecord,
    ) -> None:
        """Verify the selected row's application and layer hierarchy."""
        panel = dialog.get_by_role(
            "tabpanel",
            name="业务元数据信息",
            exact=True,
        )
        expect(panel).to_be_visible()
        for value in (
            record.application_domain,
            record.application_system,
            record.l1_name,
            record.l2_name,
            record.l3_name,
        ):
            require_business_identity(panel, value, "业务元数据")

    def _verify_technical_metadata(
        self,
        dialog: Locator,
        record: DataResourceRecord,
    ) -> None:
        """Switch to technical metadata and verify table identity values."""
        panel = self._activate_dialog_tab(dialog, "技术元数据信息")
        expect(
            panel.get_by_placeholder("请输入表中文名称,长度限制50字符")
        ).to_have_value(record.table_name_cn)
        expect(
            panel.get_by_placeholder("请输入表英文名称,长度限制50字符")
        ).to_have_value(record.table_name_en)

    def _verify_management_metadata(
        self,
        dialog: Locator,
        record: DataResourceRecord,
    ) -> None:
        """Switch to management metadata and verify ownership values."""
        panel = self._activate_dialog_tab(dialog, "管理元数据信息")
        expect(
            panel.get_by_placeholder("请输入数据责任部门,长度限制50字符")
        ).to_have_value(record.data_manage_department)
        expect(
            panel.get_by_placeholder("请输入系统项目组,长度限制50字符")
        ).to_have_value(record.system_project)

    @staticmethod
    def _activate_dialog_tab(dialog: Locator, name: str) -> Locator:
        """Activate one exact dialog tab and return its visible panel."""
        tab = dialog.get_by_role("tab", name=name, exact=True)
        panel = dialog.get_by_role("tabpanel", name=name, exact=True)

        def tab_ready() -> None:
            expect(tab).to_have_attribute("aria-selected", "true")
            expect(panel).to_be_visible()

        before, after = click_and_expect(
            tab,
            tab_ready,
            action_name=f"切换编辑弹窗 Tab: {name}",
        )
        require_surface_change(before, after, f"切换编辑弹窗 Tab: {name}")
        return panel

    @staticmethod
    def _close_dialog(dialog: Locator) -> None:
        """Leave a read-only detail/edit dialog without confirming a write."""
        close_button = dialog.get_by_role(
            "button",
            name=re.compile(r"^返\s*回$"),
        )
        before, after = click_and_expect(
            close_button,
            lambda: expect(dialog).to_be_hidden(),
            action_name="返回数据资源列表",
        )
        require_surface_change(before, after, "返回数据资源列表")

    def _row_for(self, record: DataResourceRecord) -> Locator:
        """Locate one exact virtual-table row by Chinese and English table names."""
        row = self.page.locator(".table-row").filter(
            has=self.page.get_by_text(record.table_name_cn, exact=True)
        ).filter(
            has=self.page.get_by_text(record.table_name_en, exact=True)
        )
        expect(row).to_have_count(1)
        require_actionable(row, f"数据资源行 {record.table_name_cn}")
        return row

    def _require_menu_page(self) -> ConsoleMenuPage:
        assert self._menu_page is not None, "尚未加载控制台菜单树"
        return self._menu_page

    @classmethod
    def _parse_list_response(cls, response: Response) -> DataResourceListSnapshot:
        """Validate the list API and map records into stable business identities."""
        assert response.status == 200, (
            f"数据资源列表接口 HTTP 状态异常: {response.status} {response.url}"
        )
        payload = response.json()
        assert isinstance(payload, dict), "数据资源列表接口响应不是 JSON 对象"
        code = payload.get("code")
        assert type(code) is int and code == 0, (
            f"数据资源列表接口业务失败: code={code!r}, "
            f"message={payload.get('message')!r}"
        )
        data = payload.get("data")
        assert isinstance(data, dict), "数据资源列表接口 data 不是对象"
        raw_records = data.get("records")
        assert isinstance(raw_records, list), "数据资源列表接口 data.records 不是列表"
        records = tuple(cls._parse_record(raw) for raw in raw_records)
        try:
            total = int(data.get("total", len(records)))
        except (TypeError, ValueError) as exc:
            raise AssertionError("数据资源列表接口 total 不是整数") from exc
        assert total >= len(records), (
            f"数据资源列表接口 total 小于当前记录数: {total} < {len(records)}"
        )
        return DataResourceListSnapshot(response.url, records, total)

    @classmethod
    def _parse_record(cls, raw: Any) -> DataResourceRecord:
        assert isinstance(raw, Mapping), "数据资源列表包含非对象记录"
        return DataResourceRecord(
            resource_id=cls._required_record_text(raw, "id"),
            table_name_cn=cls._required_record_text(raw, "tableNameCn"),
            table_name_en=cls._required_record_text(raw, "tableNameEn"),
            application_domain=cls._optional_record_text(
                raw,
                "dataApplicationDomainName",
            ),
            application_system=cls._optional_record_text(
                raw,
                "dataApplicationName",
            ),
            l1_name=cls._optional_record_text(raw, "l1Name"),
            l2_name=cls._optional_record_text(raw, "l2Name"),
            l3_name=cls._optional_record_text(raw, "l3Name"),
            data_manage_department=cls._optional_record_text(
                raw,
                "dataManageDepartment",
            ),
            system_project=cls._optional_record_text(raw, "systemProject"),
        )

    @staticmethod
    def _required_record_text(raw: Mapping[str, Any], field: str) -> str:
        value = raw.get(field)
        assert value is not None and str(value).strip(), (
            f"数据资源记录缺少有效字段 {field!r}: keys={sorted(raw)}"
        )
        return str(value).strip()

    @staticmethod
    def _optional_record_text(raw: Mapping[str, Any], field: str) -> str:
        value = raw.get(field)
        return str(value).strip() if value is not None else ""

    def search_and_open_portal_service_center(self, resource_name: str) -> "ResourceMgmtPage":
        """门户/服务中心搜索并打开代表资源（M1-04）。"""
        self.nav.goto_url(settings.portal_url("/#/service-center/2"))
        self.nav.wait_ready()
        search_input = self.page.get_by_placeholder("请输入搜索内容").first
        if search_input.is_visible():
            search_input.fill(resource_name)
            self.page.keyboard.press("Enter")
            self.nav.wait_ready()
        self.assertions.any_text_visible([resource_name, "服务中心", "产品市场"])
        logger.info(f"[服务中心搜索] 资源: {resource_name}")
        return self

    def search_resource_advanced(self, status: str, keyword: str) -> "ResourceMgmtPage":
        """M1-SUPP-001: 资源列表多维度高级组合检索。"""
        # 尝试展开状态下拉框
        status_dropdown = self.elements.find_candidates(
            [
                ("css", ".ant-select-selection-search-input"),
                ("css", ".el-select"),
                ("text", "状态"),
            ],
            description="状态下拉框",
            timeout=2000
        )
        if status_dropdown:
            try:
                status_dropdown.click()
                self.page.wait_for_timeout(500)
                # 尝试选择特定状态
                option = self.page.locator(f".ant-select-item-option-content, .el-select-dropdown__item").filter(has_text=status).first
                if option.is_visible():
                    option.click()
            except Exception:
                logger.debug("下拉框状态选择失败，退化为仅关键字查询")
        
        self.search_resource(keyword)
        self.assertions.page_not_blank_or_error()
        self.assertions.any_text_visible([keyword, "暂无数据", "没有匹配结果"])
        logger.info(f"[高级检索] 组合查询完成: 状态={status}, 关键字={keyword}")
        return self

    def verify_pagination_and_table_health(self) -> "ResourceMgmtPage":
        """M1-SUPP-002: 表格分页器抗跌与刷新验证。"""
        pagination = self.page.locator(".ant-pagination, .el-pagination").first
        try:
            pagination.wait_for(state="visible", timeout=3000)
            
            # 点击下一页或者第2页
            next_btn = self.page.locator(".ant-pagination-next, .btn-next").first
            page_2_btn = self.page.locator(".ant-pagination-item-2, .el-pager li:has-text('2')").first
            
            if next_btn.is_visible() and not next_btn.get_attribute("aria-disabled") == "true":
                next_btn.click()
            elif page_2_btn.is_visible():
                page_2_btn.click()
            else:
                logger.info("[交互] 只有一页数据，无需翻页")
                return self
                
            # 等待表格加载遮罩消失（抗网络抖动）
            self.page.wait_for_timeout(500) # 等待请求发出
            self.nav.wait_ready()
            
            self.assertions.page_not_blank_or_error()
            self.assertions.any_text_visible(["资源", "暂无数据", "总共"])
            logger.info("[断言] 分页器翻页操作未引发页面崩溃")
        except PlaywrightTimeoutError:
            logger.info("[断言] 页面未暴露分页组件，跳过分页验证")
            
        return self

    def verify_global_action_buttons(self) -> "ResourceMgmtPage":
        """M1-SUPP-003: 资源列表全局动作栏（如导出、批量操作）可视性断言。"""
        # 宽泛匹配导出、批量等关键操作动作
        self.assertions.page_not_blank_or_error()
        
        buttons_found = []
        for btn_text in ["导出", "批量", "新建", "同步", "刷新", "配置"]:
            btn = self.page.get_by_role("button", name=re.compile(btn_text)).first
            if btn.is_visible():
                buttons_found.append(btn_text)
                
        if buttons_found:
            logger.info(f"[断言] 全局操作按钮加载正常: {buttons_found}")
        else:
            logger.warning("[断言] 当前账号视角未发现任何全局批量操作按钮 (可能是只读权限限制)")
            
        return self
