"""Permission-management business contract tests."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from pages.console.permission_management_page import (
    ManagedUserRecord,
    OrganizationRecord,
    PermissionManagementPage,
    ResourceRecord,
    TenantRecord,
    UserRecord,
)


@dataclass
class FakeRequest:
    post_data_json: object


class FakeResponse:
    """Minimal Playwright response used by parser unit tests."""

    def __init__(
        self,
        payload: object,
        *,
        status: int = 200,
        url: str = "https://irp.example/api",
        request_body: object = None,
    ) -> None:
        self._payload = payload
        self.status = status
        self.url = url
        self.request = FakeRequest(request_body)

    def json(self) -> object:
        return self._payload


def test_resource_records_preserve_business_identity() -> None:
    response = FakeResponse(
        {
            "code": 0,
            "data": {
                "list": [
                    {"id": 3, "name": "中建云"},
                    {"id": "R-2", "name": "业务系统"},
                ]
            },
        }
    )
    assert PermissionManagementPage._resource_records(response) == (  # noqa: SLF001
        ResourceRecord("3", "中建云"),
        ResourceRecord("R-2", "业务系统"),
    )


def test_organization_records_flatten_tree_with_identity() -> None:
    response = FakeResponse(
        {
            "code": 0,
            "data": [
                {
                    "orgCode": "ROOT",
                    "orgName": "集团",
                    "children": [
                        {"orgCode": "ORG-1", "orgName": "总部", "children": []}
                    ],
                }
            ],
        }
    )
    assert PermissionManagementPage._organization_records(response) == (  # noqa: SLF001
        OrganizationRecord("ROOT", "集团"),
        OrganizationRecord("ORG-1", "总部"),
    )


def test_user_records_require_selected_resource_and_organization() -> None:
    response = FakeResponse(
        {
            "code": 0,
            "data": {"list": [{"userCode": "20431644", "userName": "测试用户"}]},
        },
        request_body={
            "queryfilter": {"resourceId": "R-1", "belongOrgCode": "ORG-1"}
        },
    )
    assert PermissionManagementPage._user_records(  # noqa: SLF001
        response, resource_id="R-1", organization_code="ORG-1"
    ) == (UserRecord("20431644", "测试用户"),)


@pytest.mark.parametrize(
    "payload,status,parser",
    [
        ({"code": 50000, "message": "系统繁忙"}, 200, "resource"),
        ({"code": 0, "data": {"list": []}}, 200, "resource"),
        ({"code": 0, "data": []}, 200, "organization"),
        ({"code": 0, "data": {}}, 500, "organization"),
        ([], 200, "resource"),
    ],
)
def test_resource_and_organization_contracts_reject_invalid_data(
    payload: object, status: int, parser: str
) -> None:
    response = FakeResponse(payload, status=status)
    with pytest.raises(AssertionError):
        if parser == "resource":
            PermissionManagementPage._resource_records(response)  # noqa: SLF001
        else:
            PermissionManagementPage._organization_records(response)  # noqa: SLF001


@pytest.mark.parametrize(
    "request_body,resource_id,organization_code",
    [
        ({}, "R-1", "ORG-1"),
        ({"queryfilter": {"resourceId": "R-2", "belongOrgCode": "ORG-1"}}, "R-1", "ORG-1"),
        ({"queryfilter": {"resourceId": "R-1", "belongOrgCode": "ORG-2"}}, "R-1", "ORG-1"),
    ],
)
def test_user_contract_rejects_wrong_request_identity(
    request_body: object, resource_id: str, organization_code: str
) -> None:
    response = FakeResponse(
        {"code": 0, "data": {"list": []}}, request_body=request_body
    )
    with pytest.raises(AssertionError):
        PermissionManagementPage._user_records(  # noqa: SLF001
            response,
            resource_id=resource_id,
            organization_code=organization_code,
        )


def test_query_value_requires_the_requested_parameter() -> None:
    assert PermissionManagementPage._query_value(  # noqa: SLF001
        "https://irp.example/permission/orgPage?resourceId=R-1", "resourceId"
    ) == "R-1"
    with pytest.raises(AssertionError):
        PermissionManagementPage._query_value(  # noqa: SLF001
            "https://irp.example/permission/orgPage", "resourceId"
        )


def _managed_user_payload(*, total: str = "1", user_code: str = "20431644") -> dict:
    return {
        "code": 0,
        "data": {
            "list": [
                {
                    "id": "USER-1",
                    "userCode": user_code,
                    "userName": "测试用户",
                    "belongOrgName": "中建数字科技有限公司",
                    "email": "t***@example.com",
                }
            ],
            "total": total,
        },
    }


def test_managed_user_query_preserves_exact_business_identity() -> None:
    expected = ManagedUserRecord(
        "USER-1",
        "20431644",
        "测试用户",
        "中建数字科技有限公司",
        "t***@example.com",
    )
    response = FakeResponse(
        _managed_user_payload(),
        request_body={"queryfilter": {"userCode": "20431644", "resourceId": 3}},
    )
    assert PermissionManagementPage._managed_user_from_list(response) == expected  # noqa: SLF001
    assert PermissionManagementPage._validate_user_query(  # noqa: SLF001
        response, "20431644"
    ) == expected


@pytest.mark.parametrize(
    "payload,request_body",
    [
        (
            _managed_user_payload(user_code="OTHER"),
            {"queryfilter": {"userCode": "20431644"}},
        ),
        (
            _managed_user_payload(total="2"),
            {"queryfilter": {"userCode": "20431644"}},
        ),
        (_managed_user_payload(), {"queryfilter": {}}),
    ],
)
def test_managed_user_query_rejects_wrong_or_non_unique_result(
    payload: dict, request_body: dict
) -> None:
    with pytest.raises(AssertionError):
        PermissionManagementPage._validate_user_query(  # noqa: SLF001
            FakeResponse(payload, request_body=request_body), "20431644"
        )


def test_user_detail_and_reset_require_the_selected_identity() -> None:
    PermissionManagementPage._validate_user_detail_request(  # noqa: SLF001
        FakeResponse(
            {"code": 0, "data": {"email": "masked"}},
            request_body={"rscId": "20431644"},
        ),
        "20431644",
    )
    PermissionManagementPage._validate_user_reset(  # noqa: SLF001
        FakeResponse(
            {"code": 0, "data": {"list": []}},
            request_body={"queryfilter": {"resourceId": 3}},
        )
    )
    with pytest.raises(AssertionError):
        PermissionManagementPage._validate_user_detail_request(  # noqa: SLF001
            FakeResponse(
                {"code": 0, "data": {}}, request_body={"rscId": "OTHER"}
            ),
            "20431644",
        )


def test_tenant_view_preserves_current_tenant_identity() -> None:
    response = FakeResponse(
        {
            "code": 0,
            "data": {"id": "100000", "tenantNo": "ZH_01_0000", "orgName": "中建云"},
        }
    )
    assert PermissionManagementPage._tenant_from_view(response) == TenantRecord(  # noqa: SLF001
        "100000", "ZH_01_0000", "中建云"
    )


def test_tenant_member_empty_query_requires_keyword_and_empty_contract() -> None:
    response = FakeResponse(
        {"code": 0, "data": {"records": [], "total": "0"}},
        request_body={"keyWord": "__ABSENT__", "tenantNo": ""},
    )
    PermissionManagementPage._validate_empty_member_query(  # noqa: SLF001
        response, "__ABSENT__"
    )
    for invalid in (
        FakeResponse(
            {"code": 0, "data": {"records": [], "total": "0"}},
            request_body={"keyWord": "OTHER"},
        ),
        FakeResponse(
            {"code": 0, "data": {"records": [{"userCode": "1"}], "total": "1"}},
            request_body={"keyWord": "__ABSENT__"},
        ),
    ):
        with pytest.raises(AssertionError):
            PermissionManagementPage._validate_empty_member_query(  # noqa: SLF001
                invalid, "__ABSENT__"
            )
