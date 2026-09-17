"""Page object for the console role-management read-only workflow."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from playwright.sync_api import Locator, Page, Response, expect

from config.settings import settings
from core.base_page import BasePage
from core.interaction_evidence import click_and_expect, require_actionable
from core.logger import get_logger


logger = get_logger("role_management_page")


@dataclass(frozen=True)
class RoleRecord:
    """Business identity for one role selected from the console list."""

    role_id: str
    name: str
    code: str


class RoleManagementPage(BasePage):
    """Control the role list, role details, and read-only permission tabs."""

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self._function_permission_panel: Locator | None = None
        self._selected_role: RoleRecord | None = None
        self._detail_dialog: Locator | None = None

    def open_console_home(self) -> "RoleManagementPage":
        """Open the split-domain console home before using its visible menu."""
        self.nav.goto_url(settings.CONSOLE_BASE_URL)
        self.page.get_by_text("权限管理", exact=True).first.wait_for(
            state="visible", timeout=settings.NAVIGATION_TIMEOUT
        )
        self.assertions.url_matches_any(["irp.cscec.com", "portal/home/workbench"], "控制台")
        logger.info("[导航] 打开控制台工作台")
        return self

    def open_from_console_menu(self) -> "RoleManagementPage":
        """Open 权限管理 -> 角色管理 through the visible console menu."""
        permission_menu = self.page.get_by_text("权限管理", exact=True).first
        require_actionable(permission_menu, "打开权限管理菜单").click()

        role_menu = self.page.get_by_text("角色管理", exact=True).first
        with self.page.expect_response(
            lambda response: "/tenant-role/pageConsole" in response.url,
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as list_capture:
            click_and_expect(
                role_menu,
                lambda: expect(
                    self.page.get_by_text("角色列表", exact=True)
                ).to_be_visible(timeout=settings.NAVIGATION_TIMEOUT),
                action_name="权限管理进入角色管理",
            )
        self._selected_role = self._role_from_list_response(list_capture.value)
        self.assertions.url_contains("roleManage")
        logger.info("[导航] 权限管理 -> 角色管理")
        return self

    def open_first_role_details(self) -> "RoleManagementPage":
        """Open the first available role without changing role data."""
        role = self.selected_role
        detail_button = self.page.get_by_role("button", name="详情", exact=True).first
        row = detail_button.locator(
            "xpath=ancestor::*[contains(concat(' ', normalize-space(@class), ' '), ' table-row ')][1]"
        )
        expect(row).to_contain_text(role.name)
        expect(row).to_contain_text(role.code)
        with self.page.expect_response(
            lambda response: "/tenant-role/pageMembers" in response.url,
            timeout=settings.ACTION_TIMEOUT,
        ) as members_capture:
            click_and_expect(
                detail_button,
                lambda: expect(
                    self.page.get_by_text("角色详情", exact=True)
                ).to_be_visible(timeout=settings.ACTION_TIMEOUT),
                action_name="打开首个角色详情",
            )
        self._validate_success_response(members_capture.value, "角色成员")
        dialog = self.page.get_by_role("dialog").filter(
            has=self.page.get_by_text("角色详情", exact=True)
        )
        expect(dialog.get_by_text(role.name, exact=True)).to_be_visible()
        expect(dialog.get_by_role("tab", name="成员", exact=True)).to_be_visible()
        self._detail_dialog = dialog
        logger.info("[只读交互] 打开角色详情: %s/%s", role.name, role.code)
        return self

    @property
    def selected_role(self) -> RoleRecord:
        """Return the role identity established by the list response."""
        assert self._selected_role is not None, "尚未从角色列表建立业务身份"
        return self._selected_role

    def should_show_members(self) -> "RoleManagementPage":
        """Require the member tab to render its identity-bearing table."""
        dialog = self._require_detail_dialog()
        member_tab = dialog.get_by_role("tab", name="成员", exact=True)
        expect(member_tab).to_have_attribute("aria-selected", "true")
        for heading in ("姓名", "用户ID", "所属组织", "操作"):
            expect(dialog.get_by_text(heading, exact=True)).to_be_visible()
        expect(dialog.get_by_role("button", name="添加成员", exact=True)).to_be_disabled()
        logger.info("[断言] 角色成员 Tab 与成员表正常渲染")
        return self

    def open_function_permissions(self) -> "RoleManagementPage":
        """Switch to 功能权限 and wait for either content or a rendered error."""
        function_tab = self.page.get_by_role("tab", name="功能权限", exact=True)
        require_actionable(function_tab, "切换角色功能权限 Tab")
        panel_id = function_tab.get_attribute("aria-controls")
        assert panel_id, "功能权限 Tab 缺少 aria-controls，无法定位内容面板"

        panel = self.page.locator(f"#{panel_id}")
        click_and_expect(
            function_tab,
            lambda: expect(function_tab).to_have_attribute("aria-selected", "true"),
            action_name="切换角色功能权限 Tab",
        )
        expect(panel).to_be_visible(timeout=settings.ACTION_TIMEOUT)

        self.page.wait_for_function(
            """panelId => {
                const panel = document.getElementById(panelId);
                return panel && (
                    panel.innerText.includes('TypeError') ||
                    panel.querySelector('.ant-tree, [role="tree"]')
                );
            }""",
            arg=panel_id,
            timeout=settings.ACTION_TIMEOUT,
        )
        self._function_permission_panel = panel
        logger.info("[只读交互] 切换到角色功能权限 Tab")
        return self

    def open_data_permissions(self) -> "RoleManagementPage":
        """Open the selected role's data-permission tab without changing it."""
        dialog = self._require_detail_dialog()
        data_tab = dialog.get_by_role("tab", name="数据权限", exact=True)
        with self.page.expect_response(
            lambda response: "/tenant-role/getDataPermissionDimensionConfig" in response.url,
            timeout=settings.ACTION_TIMEOUT,
        ) as config_capture:
            with self.page.expect_response(
                lambda response: "/tenant-role/getDataPermission?" in response.url,
                timeout=settings.ACTION_TIMEOUT,
            ) as permission_capture:
                click_and_expect(
                    data_tab,
                    lambda: expect(data_tab).to_have_attribute("aria-selected", "true"),
                    action_name="切换角色数据权限 Tab",
                )
        self._validate_success_response(config_capture.value, "数据权限维度")
        self._validate_success_response(permission_capture.value, "角色数据权限")
        panel_id = data_tab.get_attribute("aria-controls")
        assert panel_id, "数据权限 Tab 缺少 aria-controls"
        panel = self.page.locator(f"#{panel_id}")
        expect(panel).to_be_visible()
        for dimension in ("所属租户", "后端类目", "领域"):
            expect(panel.get_by_text(dimension, exact=True)).to_be_visible()
        switches = panel.get_by_role("switch", name="全量数据", exact=True)
        assert switches.count() >= 3, "数据权限缺少预期的全量数据开关"
        for index in range(3):
            expect(switches.nth(index)).to_be_checked()
            expect(switches.nth(index)).to_be_disabled()
        logger.info("[只读交互] 角色数据权限维度与全量状态正常")
        return self

    def open_edit_readonly_and_cancel(self) -> "RoleManagementPage":
        """Inspect role edit values and close without changing or saving them."""
        role = self.selected_role
        detail_dialog = self._require_detail_dialog()
        edit_button = detail_dialog.get_by_role("button", name="edit", exact=True)
        click_and_expect(
            edit_button,
            lambda: expect(self.page.get_by_text("角色修改", exact=True)).to_be_visible(),
            action_name="打开角色修改弹窗",
        )
        edit_dialog = self.page.get_by_role("dialog").filter(
            has=self.page.get_by_text("角色修改", exact=True)
        ).last
        name_input = edit_dialog.get_by_role(
            "textbox", name="请输入角色名称", exact=True
        )
        expect(name_input).to_have_value(role.name)
        description = edit_dialog.get_by_role(
            "textbox",
            name="明确角色含义，能让团队成员直观了解该角色具备的权限",
            exact=True,
        )
        expect(description).not_to_be_empty()
        expect(edit_dialog.get_by_text("角色分类", exact=True)).to_be_visible()
        expect(edit_dialog.get_by_role("button", name="保 存", exact=True)).to_be_disabled()
        cancel = edit_dialog.get_by_role("button", name="取 消", exact=True)
        cancel_prompt = self.page.get_by_text(
            re.compile(r"是否取消当前操作[?？]?"), exact=False
        )
        click_and_expect(
            cancel,
            lambda: expect(cancel_prompt).to_be_visible(),
            action_name="取消角色修改",
        )
        confirmation = self.page.get_by_role("dialog").filter(
            has=cancel_prompt
        ).last
        click_and_expect(
            confirmation.get_by_role("button", name=re.compile(r"^确\s*定$")),
            lambda: expect(name_input).to_be_hidden(),
            action_name="确认取消角色修改",
        )
        logger.info("[只读交互] 角色编辑回显正常并已取消，未保存")
        return self

    def _require_detail_dialog(self) -> Locator:
        assert self._detail_dialog is not None, "尚未打开角色详情"
        return self._detail_dialog

    @classmethod
    def _role_from_list_response(cls, response: Response) -> RoleRecord:
        """Parse the first role identity from a successful list response."""
        payload = cls._response_payload(response, "角色列表")
        records = cls._records(payload.get("data"))
        assert records, "角色列表接口未返回可用角色"
        raw = records[0]
        assert isinstance(raw, dict), "角色列表首条记录结构无效"
        return RoleRecord(
            role_id=cls._required_field(raw, "id", "roleId"),
            name=cls._required_field(raw, "roleName", "name"),
            code=cls._required_field(raw, "roleCode", "code"),
        )

    @classmethod
    def _validate_success_response(cls, response: Response, label: str) -> dict[str, Any]:
        """Require HTTP and business success for a role-management response."""
        return cls._response_payload(response, label)

    @staticmethod
    def _response_payload(response: Response, label: str) -> dict[str, Any]:
        assert response.status == 200, f"{label}接口 HTTP 失败: {response.status}"
        payload = response.json()
        assert isinstance(payload, dict), f"{label}接口响应不是对象"
        assert payload.get("code") in (0, 200, "0", "200"), (
            f"{label}接口业务失败: {payload.get('code')}/{payload.get('message') or payload.get('msg')}"
        )
        return payload

    @staticmethod
    def _records(data: Any) -> list[Any]:
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        for key in ("records", "list", "rows", "content"):
            value = data.get(key)
            if isinstance(value, list):
                return value
        return []

    @staticmethod
    def _required_field(raw: dict[str, Any], *names: str) -> str:
        for name in names:
            value = raw.get(name)
            if value is not None and str(value).strip():
                return str(value).strip()
        raise AssertionError(f"角色记录缺少字段: {'/'.join(names)}")

    def should_show_function_permission_tree(self) -> "RoleManagementPage":
        """Assert that function permissions render as a tree without an error view."""
        assert self._function_permission_panel is not None, "尚未打开功能权限 Tab"
        panel = self._function_permission_panel
        error_text = panel.get_by_text("TypeError", exact=True)
        assert error_text.count() == 0, "角色功能权限内容区渲染 TypeError"

        permission_tree = panel.locator(".ant-tree, [role='tree']").first
        permission_tree.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        logger.info("[断言] 角色功能权限树正常渲染")
        return self
