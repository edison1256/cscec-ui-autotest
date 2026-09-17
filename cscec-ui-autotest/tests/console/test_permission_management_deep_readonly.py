"""Deep read-only candidates for permission-management login pages."""

from __future__ import annotations

import pytest

from core.browser_health import BrowserHealthMonitor
from pages.console.permission_management_page import PermissionManagementPage


@pytest.mark.console
@pytest.mark.readonly
@pytest.mark.regression
@pytest.mark.domain_split
@pytest.mark.prod_conditional
class TestPermissionManagementDeepReadonly:
    """Inspect login authorization pages without invoking authorization actions."""

    def test_4a_login_resource_organization_and_users(self, logged_in_page) -> None:
        """PERM-LOGIN-001: verify 4A resources, organizations, users and levels."""
        permission_page = PermissionManagementPage(logged_in_page).open_console_home()
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            "PERM-LOGIN-001",
            "4A登录资源、组织和部门用户只读探查",
        ).start()
        try:
            permission_page.open_4a_login()
            permission_page.verify_4a_structure_and_select_organization()
        finally:
            health.stop()
        health.assert_healthy()

    def test_organization_login_resource_and_tree(self, logged_in_page) -> None:
        """PERM-LOGIN-002: verify organization-login resource tree and levels."""
        permission_page = PermissionManagementPage(logged_in_page).open_console_home()
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            "PERM-LOGIN-002",
            "组织登录资源和组织树只读探查",
        ).start()
        try:
            permission_page.open_organization_login()
            permission_page.verify_organization_login_structure()
        finally:
            health.stop()
        health.assert_healthy()

    def test_user_list_exact_query_detail_and_reset(self, logged_in_page) -> None:
        """PERM-USER-001: verify the current user's query, detail, and reset flow."""
        permission_page = PermissionManagementPage(logged_in_page).open_console_home()
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            "PERM-USER-001",
            "用户列表、精确查询、详情和重置只读探查",
        ).start()
        try:
            permission_page.open_user_management()
            permission_page.query_open_and_reset_selected_user()
        finally:
            health.stop()
        health.assert_healthy()

    def test_current_tenant_identity_and_empty_member_query(self, logged_in_page) -> None:
        """PERM-TENANT-001: verify 中建云 and a strict empty member query."""
        permission_page = PermissionManagementPage(logged_in_page).open_console_home()
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            "PERM-TENANT-001",
            "中建云租户身份和成员空结果只读探查",
        ).start()
        try:
            permission_page.open_tenant_management()
            permission_page.verify_tenant_member_empty_query()
        finally:
            health.stop()
        health.assert_healthy()
