"""PROD role-management deep read-only regression."""

from __future__ import annotations

import pytest

from core.browser_health import BrowserHealthMonitor, BusinessResponseRule
from pages.console.role_management_page import RoleManagementPage


@pytest.mark.console
@pytest.mark.smoke
@pytest.mark.readonly
@pytest.mark.regression
@pytest.mark.domain_split
@pytest.mark.prod_mandatory
class TestRoleManagementReadonlyRegression:
    """Cover list -> details -> permission-tab rendering through the real UI path."""

    def test_first_role_function_permissions_render_without_runtime_error(
        self, logged_in_page
    ) -> None:
        """C-P0-CONSOLE-014: a role's function-permission tree renders safely."""
        role_page = RoleManagementPage(logged_in_page).open_console_home()

        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            "C-P0-CONSOLE-014",
            "角色管理首个角色的功能权限 Tab",
        ).start()
        try:
            role_page.open_from_console_menu().open_first_role_details()
            role_page.open_function_permissions()
        finally:
            health.stop()

        health.assert_healthy()
        role_page.should_show_function_permission_tree()


@pytest.mark.console
@pytest.mark.readonly
@pytest.mark.regression
@pytest.mark.domain_split
class TestRoleManagementDeepReadonlyCandidate:
    """Candidate coverage that remains outside the production default gate."""

    def test_role_members_data_permissions_and_edit_preview(
        self, logged_in_page
    ) -> None:
        """PERM-ROLE-001: inspect one role deeply without changing it."""
        role_page = RoleManagementPage(logged_in_page).open_console_home()
        health = BrowserHealthMonitor(
            logged_in_page,
            "角色成员、数据权限和编辑确认前",
            business_rules=(
                BusinessResponseRule(r"/tenant-role/pageConsole$"),
                BusinessResponseRule(r"/tenant-role/pageMembers$"),
                BusinessResponseRule(r"/tenant-role/getDataPermissionDimensionConfig[?]"),
                BusinessResponseRule(r"/tenant-role/getDataPermission[?]"),
            ),
        ).start()
        try:
            role_page.open_from_console_menu().open_first_role_details()
            role_page.should_show_members()
            role_page.open_data_permissions()
            role_page.open_edit_readonly_and_cancel()
        finally:
            health.stop()

        health.assert_healthy()
