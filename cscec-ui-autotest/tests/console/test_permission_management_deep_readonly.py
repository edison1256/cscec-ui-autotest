"""Deep read-only candidates for permission-management login pages."""

from __future__ import annotations

import pytest

from core.browser_health import BrowserHealthMonitor, BusinessResponseRule
from pages.console.permission_management_page import PermissionManagementPage


@pytest.mark.console
@pytest.mark.readonly
@pytest.mark.regression
@pytest.mark.domain_split
class TestPermissionManagementDeepReadonly:
    """Inspect login authorization pages without invoking authorization actions."""

    def test_4a_login_resource_organization_and_users(self, logged_in_page) -> None:
        """PERM-LOGIN-001: verify 4A resources, organizations, users and levels."""
        permission_page = PermissionManagementPage(logged_in_page).open_console_home()
        health = BrowserHealthMonitor(
            logged_in_page,
            "4A登录资源、组织和部门用户只读探查",
            business_rules=(
                BusinessResponseRule(r"/cloud/page$"),
                BusinessResponseRule(r"/permission/userPage$"),
            ),
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
        health = BrowserHealthMonitor(
            logged_in_page,
            "组织登录资源和组织树只读探查",
            business_rules=(
                BusinessResponseRule(r"/cloud/page$"),
                BusinessResponseRule(r"/permission/orgPage[?]"),
            ),
        ).start()
        try:
            permission_page.open_organization_login()
            permission_page.verify_organization_login_structure()
        finally:
            health.stop()
        health.assert_healthy()
