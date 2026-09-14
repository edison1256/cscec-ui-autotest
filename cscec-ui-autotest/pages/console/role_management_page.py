"""Page object for the console role-management read-only workflow."""

from __future__ import annotations

from playwright.sync_api import Locator, Page, expect

from config.settings import settings
from core.base_page import BasePage
from core.logger import get_logger


logger = get_logger("role_management_page")


class RoleManagementPage(BasePage):
    """Control the role list, role details, and read-only permission tabs."""

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self._function_permission_panel: Locator | None = None

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
        permission_menu.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        permission_menu.click()

        role_menu = self.page.get_by_text("角色管理", exact=True).first
        role_menu.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        role_menu.click()

        self.page.get_by_text("角色列表", exact=True).wait_for(
            state="visible", timeout=settings.NAVIGATION_TIMEOUT
        )
        self.assertions.url_contains("roleManage")
        logger.info("[导航] 权限管理 -> 角色管理")
        return self

    def open_first_role_details(self) -> "RoleManagementPage":
        """Open the first available role without changing role data."""
        detail_button = self.page.get_by_role("button", name="详情", exact=True).first
        detail_button.wait_for(state="visible", timeout=settings.NAVIGATION_TIMEOUT)
        detail_button.click()

        self.page.get_by_text("角色详情", exact=True).wait_for(
            state="visible", timeout=settings.ACTION_TIMEOUT
        )
        self.page.get_by_role("tab", name="成员", exact=True).wait_for(
            state="visible", timeout=settings.ACTION_TIMEOUT
        )
        logger.info("[只读交互] 打开首个角色详情")
        return self

    def open_function_permissions(self) -> "RoleManagementPage":
        """Switch to 功能权限 and wait for either content or a rendered error."""
        function_tab = self.page.get_by_role("tab", name="功能权限", exact=True)
        function_tab.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        panel_id = function_tab.get_attribute("aria-controls")
        assert panel_id, "功能权限 Tab 缺少 aria-controls，无法定位内容面板"

        function_tab.click()
        expect(function_tab).to_have_attribute("aria-selected", "true")
        panel = self.page.locator(f"#{panel_id}")
        panel.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)

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
