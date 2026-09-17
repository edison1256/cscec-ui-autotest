"""Read-only page object for console permission-management login pages."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

from playwright.sync_api import Page, Response, expect

from config.settings import settings
from core.base_page import BasePage
from core.interaction_evidence import click_and_expect, require_actionable
from core.logger import get_logger


logger = get_logger("permission_management_page")


@dataclass(frozen=True)
class ResourceRecord:
    """Identity for one login-authorizable resource."""

    resource_id: str
    name: str


@dataclass(frozen=True)
class OrganizationRecord:
    """Identity for one organization node."""

    code: str
    name: str


@dataclass(frozen=True)
class UserRecord:
    """Identity for one department user."""

    code: str
    name: str


@dataclass(frozen=True)
class ManagedUserRecord:
    """Identity and display fields for one console-managed user."""

    record_id: str
    code: str
    name: str
    organization: str
    email: str


@dataclass(frozen=True)
class TenantRecord:
    """Identity for one tenant selected in tenant management."""

    tenant_id: str
    number: str
    name: str


class PermissionManagementPage(BasePage):
    """Inspect permission-management pages without changing authorization data."""

    def __init__(self, page: Page) -> None:
        super().__init__(page)
        self._resources: tuple[ResourceRecord, ...] = ()
        self._organizations: tuple[OrganizationRecord, ...] = ()
        self._selected_resource: ResourceRecord | None = None
        self._selected_user: ManagedUserRecord | None = None
        self._selected_tenant: TenantRecord | None = None

    def open_console_home(self) -> "PermissionManagementPage":
        """Open the split-domain console home."""
        self.nav.goto_url(settings.CONSOLE_BASE_URL)
        self.page.get_by_text("权限管理", exact=True).first.wait_for(
            state="visible", timeout=settings.NAVIGATION_TIMEOUT
        )
        self.assertions.url_matches_any(["irp.cscec.com", "portal/home/workbench"], "控制台")
        return self

    def open_4a_login(self) -> "PermissionManagementPage":
        """Open 4A登录 and establish resource and organization identities."""
        self._open_login_management()
        with self.page.expect_response(
            lambda response: "/cloud/page" in response.url,
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as resource_capture:
            self._click_login_leaf("4A登录", "4A登录管理")

        resource_response = resource_capture.value
        self._resources = self._resource_records(resource_response)
        organization_payload = self._fetch_business_payload(
            "/basedata/zjCompany/getZjCompanyTree?containDept=true",
            source_response=resource_response,
            label="授权组织",
        )
        self._organizations = self._organization_records_from_payload(
            organization_payload
        )
        self._selected_resource = self._selected_resource_from_ui()
        self.assertions.url_contains("loginManage/userLogin")
        logger.info("[导航] 权限管理 -> 登录管理 -> 4A登录")
        return self

    def verify_4a_structure_and_select_organization(
        self,
    ) -> "PermissionManagementPage":
        """Validate the 4A structure and load users for one dynamic organization."""
        self._verify_common_login_controls("4A登录管理")
        tree = self.page.get_by_role("tree")
        expect(tree).to_be_visible()

        titles = tree.locator(".ant-tree-title")
        assert titles.count() >= 2, "4A组织树缺少可选择的子组织"
        target = titles.nth(1)
        target_name = target.inner_text().strip()
        organization = self._organization_by_name(target_name)

        with self.page.expect_response(
            lambda response: "/permission/userPage" in response.url,
            timeout=settings.ACTION_TIMEOUT,
        ) as user_capture:
            click_and_expect(
                target,
                lambda: expect(target.locator("..")).to_have_class(
                    re.compile(r"selected")
                ),
                action_name="选择4A组织节点",
            )

        users = self._user_records(
            user_capture.value,
            resource_id=self.selected_resource.resource_id,
            organization_code=organization.code,
        )
        if users:
            first_user = users[0]
            expect(self.page.get_by_text(first_user.code, exact=True)).to_be_visible()
            expect(self.page.get_by_text(first_user.name, exact=True)).to_be_visible()
        else:
            expect(self.page.get_by_text("暂无数据", exact=True)).to_be_visible()
        logger.info("[只读交互] 4A组织与部门用户接口身份一致: %s", organization.name)
        return self

    def open_organization_login(self) -> "PermissionManagementPage":
        """Open 组织登录 and establish the selected resource's organization tree."""
        self._open_login_management()
        with self.page.expect_response(
            lambda response: "/cloud/page" in response.url,
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as resource_capture:
            self._click_login_leaf("组织登录", "组织登录管理")

        resource_response = resource_capture.value
        self._resources = self._resource_records(resource_response)
        self._selected_resource = self._selected_resource_from_ui()
        organization_payload = self._fetch_business_payload(
            "/irp-api/irp-portal-console/permission/orgPage"
            f"?resourceId={self.selected_resource.resource_id}",
            source_response=resource_response,
            label="授权组织",
        )
        self._organizations = self._organization_records_from_payload(
            organization_payload
        )
        self.assertions.url_contains("loginManage/orgLogin")
        logger.info("[导航] 权限管理 -> 登录管理 -> 组织登录")
        return self

    def verify_organization_login_structure(self) -> "PermissionManagementPage":
        """Validate organization-login identities without changing authorization."""
        self._verify_common_login_controls("组织登录管理")
        assert self._organizations, "组织登录接口未返回组织"
        root = self._organizations[0]
        expect(self.page.get_by_text(root.name, exact=True)).to_be_visible()
        logger.info(
            "[只读交互] 组织登录资源与组织树一致: %s/%s",
            self.selected_resource.name,
            root.name,
        )
        return self

    def open_user_management(self) -> "PermissionManagementPage":
        """Open user management and validate its initial list response."""
        self._open_permission_management()
        with self.page.expect_response(
            lambda response: "/permission/page" in response.url,
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as list_capture:
            self._click_permission_leaf("用户管理", "用户列表")
        self._success_payload(list_capture.value, "用户列表")
        self.assertions.url_contains("userManage/user")
        logger.info("[导航] 权限管理 -> 用户管理")
        return self

    def query_open_and_reset_selected_user(self) -> "PermissionManagementPage":
        """Query the authenticated user, inspect its detail, return, and reset."""
        assert settings.USERNAME, "当前环境未配置登录用户 ID"
        user_id = self.page.get_by_placeholder("请输入用户ID")
        user_id.fill(settings.USERNAME)
        with self.page.expect_response(
            lambda response: "/permission/page" in response.url,
            timeout=settings.ACTION_TIMEOUT,
        ) as query_capture:
            self.page.get_by_role("button", name="查 询", exact=True).click()
        user = self._validate_user_query(query_capture.value, settings.USERNAME)
        self._selected_user = user
        row = self.page.locator(".table-row").filter(
            has=self.page.get_by_text(user.code, exact=True)
        )
        expect(row).to_have_count(1)
        expect(row).to_contain_text(user.name)
        expect(row).to_contain_text(user.organization)

        with self.page.expect_response(
            lambda response: "/resource-encrypt/getDecryptInfo" in response.url,
            timeout=settings.ACTION_TIMEOUT,
        ) as detail_capture:
            row.get_by_text("详情", exact=True).click()
        self._validate_user_detail_request(detail_capture.value, user.code)
        dialog = self.page.get_by_role("dialog").filter(
            has=self.page.get_by_text("用户详情", exact=True)
        )
        expect(dialog.locator('input:disabled[value="' + user.name + '"]')).to_be_visible()
        expect(dialog.locator('input:disabled[value="' + user.code + '"]')).to_be_visible()
        expect(
            dialog.locator('input:disabled[value="' + user.organization + '"]')
        ).to_be_visible()
        if user.email:
            expect(dialog.locator('input:disabled[value="' + user.email + '"]')).to_be_visible()
        click_and_expect(
            dialog.get_by_role("button", name="返 回", exact=True),
            lambda: expect(dialog).to_be_hidden(),
            action_name="关闭用户详情",
        )

        with self.page.expect_response(
            lambda response: "/permission/page" in response.url,
            timeout=settings.ACTION_TIMEOUT,
        ) as reset_capture:
            self.page.get_by_role("button", name="重 置", exact=True).click()
        self._validate_user_reset(reset_capture.value)
        expect(user_id).to_have_value("")
        logger.info("[只读交互] 用户精确查询、详情回显和重置完成: %s", user.code)
        return self

    def open_tenant_management(self) -> "PermissionManagementPage":
        """Open tenant management and validate the fixed current tenant identity."""
        self._open_permission_management()
        with self.page.expect_response(
            lambda response: "/tenant/findAll" in response.url,
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as tree_capture:
            self._click_permission_leaf("租户管理", "成员")
        assert tree_capture.value.status == 200, (
            f"租户树接口 HTTP 失败: {tree_capture.value.status}"
        )
        tenant_title = self.page.get_by_text("中建云（ZH_01_0000）", exact=True)
        expect(tenant_title).to_be_visible()
        with self.page.expect_response(
            lambda response: "/tenant/view?" in response.url,
            timeout=settings.ACTION_TIMEOUT,
        ) as tenant_capture:
            tenant_title.click()
        self._selected_tenant = self._tenant_from_view(tenant_capture.value)
        assert self._selected_tenant == TenantRecord("100000", "ZH_01_0000", "中建云")
        self.assertions.url_contains("tenant/tenantManage")
        logger.info("[导航] 权限管理 -> 租户管理 -> 中建云")
        return self

    def verify_tenant_member_empty_query(self) -> "PermissionManagementPage":
        """Search a unique absent member and require API/UI empty-state agreement."""
        for pattern in (
            r"^待加入成员\s*$",
            r"^批量移出\s*$",
            r"^添加租户成员\s*$",
        ):
            expect(self.page.get_by_text(re.compile(pattern))).to_be_visible()

        keyword = f"__NO_SUCH_MEMBER_{datetime.now():%Y%m%d%H%M%S%f}__"
        search = self.page.get_by_placeholder("请输入租户名称、用户名称或者用户ID")
        search.fill(keyword)
        with self.page.expect_response(
            lambda response: "/tenant-member/page" in response.url,
            timeout=settings.ACTION_TIMEOUT,
        ) as member_capture:
            search.press("Enter")
        self._validate_empty_member_query(member_capture.value, keyword)
        expect(self.page.locator("#userTable").get_by_text("暂无数据", exact=True)).to_be_visible()
        logger.info("[只读交互] 中建云租户成员空结果与页面一致")
        return self

    @property
    def selected_resource(self) -> ResourceRecord:
        """Return the resource selected by the page."""
        assert self._selected_resource is not None, "尚未建立当前资源身份"
        return self._selected_resource

    @property
    def selected_user(self) -> ManagedUserRecord:
        """Return the authenticated user selected by the exact query."""
        assert self._selected_user is not None, "尚未建立用户身份"
        return self._selected_user

    def _open_permission_management(self) -> None:
        permission_menu = self.page.get_by_text("权限管理", exact=True).first
        require_actionable(permission_menu, "打开权限管理菜单").click()

    def _click_permission_leaf(self, leaf_name: str, heading: str) -> None:
        leaf = self.page.get_by_text(leaf_name, exact=True).first
        click_and_expect(
            leaf,
            lambda: expect(self.page.get_by_text(heading, exact=True)).to_be_visible(
                timeout=settings.NAVIGATION_TIMEOUT
            ),
            action_name=f"进入{leaf_name}",
        )

    def _open_login_management(self) -> None:
        self._open_permission_management()
        login_menu = self.page.get_by_text("登录管理", exact=True).first
        click_and_expect(
            login_menu,
            lambda: expect(self.page.get_by_text("4A登录", exact=True)).to_be_visible(),
            action_name="展开登录管理菜单",
        )

    def _click_login_leaf(self, leaf_name: str, heading: str) -> None:
        leaf = self.page.get_by_text(leaf_name, exact=True).first
        click_and_expect(
            leaf,
            lambda: expect(self.page.get_by_text(heading, exact=True)).to_be_visible(
                timeout=settings.NAVIGATION_TIMEOUT
            ),
            action_name=f"进入{leaf_name}",
        )

    def _verify_common_login_controls(self, heading: str) -> None:
        expect(self.page.get_by_text(heading, exact=True)).to_be_visible()
        selected = self.selected_resource
        resource_radio = self.page.locator(
            f'input[type="radio"][value="{selected.resource_id}"]'
        )
        expect(resource_radio).to_be_checked()
        expect(resource_radio.locator("xpath=ancestor::label")).to_contain_text(
            selected.name
        )
        expect(self.page.get_by_role("button", name="授权登录", exact=True)).to_be_visible()
        expect(self.page.get_by_role("button", name="取消授权", exact=True)).to_be_visible()
        expect(self.page.locator('input[type="radio"][value="1"]')).to_be_checked()
        expect(self.page.locator('input[type="radio"][value="2"]')).not_to_be_checked()

    def _selected_resource_from_ui(self) -> ResourceRecord:
        resource_ids = [resource.resource_id for resource in self._resources]
        self.page.wait_for_function(
            """ids => [...document.querySelectorAll('input[type="radio"]:checked')]
                .some(input => ids.includes(input.value))""",
            arg=resource_ids,
            timeout=settings.ACTION_TIMEOUT,
        )
        checked = self.page.locator('input[type="radio"]:checked')
        for index in range(checked.count()):
            value = checked.nth(index).get_attribute("value") or ""
            match = next(
                (resource for resource in self._resources if resource.resource_id == value),
                None,
            )
            if match is not None:
                return match
        raise AssertionError("资源接口与页面当前选中资源不一致")

    def _organization_by_name(self, name: str) -> OrganizationRecord:
        for organization in self._organizations:
            if organization.name == name:
                return organization
        raise AssertionError(f"组织接口缺少页面节点: {name}")

    @classmethod
    def _resource_records(cls, response: Response) -> tuple[ResourceRecord, ...]:
        payload = cls._success_payload(response, "授权资源")
        data = payload.get("data")
        assert isinstance(data, dict), "授权资源接口 data 不是对象"
        rows = data.get("list")
        assert isinstance(rows, list) and rows, "授权资源接口未返回资源列表"
        records = tuple(
            ResourceRecord(
                cls._required_field(row, "id"),
                cls._required_field(row, "name"),
            )
            for row in rows
            if isinstance(row, dict)
        )
        assert records, "授权资源接口没有有效资源身份"
        return records

    @classmethod
    def _organization_records(
        cls, response: Response
    ) -> tuple[OrganizationRecord, ...]:
        payload = cls._success_payload(response, "授权组织")
        return cls._organization_records_from_payload(payload)

    @classmethod
    def _organization_records_from_payload(
        cls, payload: dict[str, Any]
    ) -> tuple[OrganizationRecord, ...]:
        roots = payload.get("data")
        if isinstance(roots, dict):
            roots = roots.get("list") or roots.get("records") or roots.get("children")
        assert isinstance(roots, list) and roots, "授权组织接口未返回组织树"
        records: list[OrganizationRecord] = []

        def collect(nodes: list[Any]) -> None:
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                code = node.get("orgCode") or node.get("code") or node.get("id")
                name = node.get("orgName") or node.get("name") or node.get("title")
                if code is not None and name is not None:
                    records.append(OrganizationRecord(str(code).strip(), str(name).strip()))
                children = node.get("children")
                if isinstance(children, list):
                    collect(children)

        collect(roots)
        assert records, "授权组织接口没有有效组织身份"
        return tuple(records)

    def _fetch_business_payload(
        self,
        path: str,
        *,
        source_response: Response,
        label: str,
    ) -> dict[str, Any]:
        """Fetch a large read-only payload with the page's original auth headers."""
        original_headers = source_response.request.all_headers()
        retry_headers = {
            name: value
            for name, value in original_headers.items()
            if name.lower() in {"authorization", "env", "user-token"}
        }
        parsed = urlparse(self.page.url)
        url = f"{parsed.scheme}://{parsed.netloc}{path}"
        payload = self.page.evaluate(
            """async ({ url, headers }) => {
                const response = await fetch(url, {
                    credentials: 'include',
                    headers,
                });
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }
                return response.json();
            }""",
            {"url": url, "headers": retry_headers},
        )
        validated = self._validate_payload(payload, label)
        logger.info("[接口] 从当前登录页面读取只读业务数据: %s", label)
        return validated

    @classmethod
    def _user_records(
        cls,
        response: Response,
        *,
        resource_id: str,
        organization_code: str,
    ) -> tuple[UserRecord, ...]:
        request_body = response.request.post_data_json
        assert isinstance(request_body, dict), "部门用户请求体不是对象"
        query = request_body.get("queryfilter")
        assert isinstance(query, dict), "部门用户请求缺少 queryfilter"
        assert str(query.get("resourceId")) == resource_id, "部门用户请求资源身份错误"
        assert str(query.get("belongOrgCode")) == organization_code, "部门用户请求组织身份错误"

        payload = cls._success_payload(response, "部门用户")
        data = payload.get("data")
        assert isinstance(data, dict), "部门用户接口 data 不是对象"
        rows = data.get("list")
        assert isinstance(rows, list), "部门用户接口 data.list 不是列表"
        return tuple(
            UserRecord(
                cls._required_field(row, "userCode"),
                cls._required_field(row, "userName"),
            )
            for row in rows
            if isinstance(row, dict)
        )

    @classmethod
    def _managed_user_from_list(cls, response: Response) -> ManagedUserRecord:
        payload = cls._success_payload(response, "用户列表")
        data = payload.get("data")
        assert isinstance(data, dict), "用户列表接口 data 不是对象"
        rows = data.get("list")
        assert isinstance(rows, list) and rows, "用户列表接口未返回用户"
        for row in rows:
            if not isinstance(row, dict):
                continue
            required = ("id", "userCode", "userName", "belongOrgName")
            if all(row.get(name) is not None and str(row[name]).strip() for name in required):
                return ManagedUserRecord(
                    record_id=str(row["id"]).strip(),
                    code=str(row["userCode"]).strip(),
                    name=str(row["userName"]).strip(),
                    organization=str(row["belongOrgName"]).strip(),
                    email=str(row.get("email") or "").strip(),
                )
        raise AssertionError("用户列表没有字段完整的可验证用户")

    @classmethod
    def _validate_user_query(
        cls, response: Response, expected_code: str
    ) -> ManagedUserRecord:
        body = response.request.post_data_json
        assert isinstance(body, dict), "用户查询请求体不是对象"
        query = body.get("queryfilter")
        assert isinstance(query, dict), "用户查询缺少 queryfilter"
        assert str(query.get("userCode")) == expected_code, "用户查询未携带精确用户 ID"
        actual = cls._managed_user_from_list(response)
        assert actual.code == expected_code, "用户查询返回了不同业务对象"
        data = cls._success_payload(response, "用户查询").get("data")
        assert isinstance(data, dict) and str(data.get("total")) == "1", (
            "用户精确查询未返回唯一结果"
        )
        return actual

    @classmethod
    def _validate_user_detail_request(cls, response: Response, user_code: str) -> None:
        payload = cls._success_payload(response, "用户详情")
        body = response.request.post_data_json
        assert isinstance(body, dict), "用户详情请求体不是对象"
        assert str(body.get("rscId")) == user_code, "用户详情请求了不同用户"
        assert payload.get("data") is not None, "用户详情接口缺少 data"

    @classmethod
    def _validate_user_reset(cls, response: Response) -> None:
        body = response.request.post_data_json
        assert isinstance(body, dict), "用户重置请求体不是对象"
        query = body.get("queryfilter")
        assert isinstance(query, dict), "用户重置请求缺少 queryfilter"
        assert not query.get("userCode"), "重置后仍携带用户 ID"
        cls._success_payload(response, "用户重置")

    @classmethod
    def _tenant_from_view(cls, response: Response) -> TenantRecord:
        payload = cls._success_payload(response, "租户详情")
        data = payload.get("data")
        assert isinstance(data, dict), "租户详情接口 data 不是对象"
        return TenantRecord(
            tenant_id=cls._required_field(data, "id"),
            number=cls._required_field(data, "tenantNo"),
            name=cls._required_field(data, "orgName"),
        )

    @classmethod
    def _validate_empty_member_query(cls, response: Response, keyword: str) -> None:
        body = response.request.post_data_json
        assert isinstance(body, dict), "租户成员查询请求体不是对象"
        assert body.get("keyWord") == keyword, "租户成员查询未携带本次关键字"
        payload = cls._success_payload(response, "租户成员")
        data = payload.get("data")
        assert isinstance(data, dict), "租户成员接口 data 不是对象"
        assert data.get("records") == [], "不存在成员查询返回了记录"
        assert str(data.get("total")) == "0", "不存在成员查询 total 非零"

    @staticmethod
    def _success_payload(response: Response, label: str) -> dict[str, Any]:
        assert response.status == 200, f"{label}接口 HTTP 失败: {response.status}"
        payload = response.json()
        return PermissionManagementPage._validate_payload(payload, label)

    @staticmethod
    def _validate_payload(payload: Any, label: str) -> dict[str, Any]:
        assert isinstance(payload, dict), f"{label}接口响应不是对象"
        assert payload.get("code") in (0, 200, "0", "200"), (
            f"{label}接口业务失败: {payload.get('code')}/"
            f"{payload.get('message') or payload.get('msg')}"
        )
        return payload

    @staticmethod
    def _required_field(row: dict[str, Any], name: str) -> str:
        value = row.get(name)
        assert value is not None and str(value).strip(), f"业务记录缺少字段: {name}"
        return str(value).strip()

    @staticmethod
    def _query_value(url: str, name: str) -> str:
        values = parse_qs(urlparse(url).query).get(name)
        assert values and values[0], f"接口 URL 缺少查询参数: {name}"
        return values[0]
