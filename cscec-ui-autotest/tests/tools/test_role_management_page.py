"""Role-management business identity contract tests."""

from __future__ import annotations

import pytest

from pages.console.role_management_page import RoleManagementPage, RoleRecord


class FakeResponse:
    """Minimal Playwright response used by parser unit tests."""

    def __init__(self, payload: object, status: int = 200) -> None:
        self._payload = payload
        self.status = status

    def json(self) -> object:
        return self._payload


@pytest.mark.parametrize(
    "payload,status,expected",
    [
        (
            {
                "code": 0,
                "data": {
                    "records": [
                        {"id": 100007, "roleName": "平台运营主管", "roleCode": "100-007"}
                    ]
                },
            },
            200,
            RoleRecord("100007", "平台运营主管", "100-007"),
        ),
        (
            {
                "code": "200",
                "data": {
                    "list": [
                        {"roleId": "R-1", "name": "测试角色", "code": "ROLE-1"}
                    ]
                },
            },
            200,
            RoleRecord("R-1", "测试角色", "ROLE-1"),
        ),
    ],
)
def test_role_list_preserves_business_identity(
    payload: dict, status: int, expected: RoleRecord
) -> None:
    assert RoleManagementPage._role_from_list_response(  # noqa: SLF001
        FakeResponse(payload, status)
    ) == expected


@pytest.mark.parametrize(
    "payload,status",
    [
        ({"code": 50000, "message": "系统繁忙", "data": {"records": []}}, 200),
        ({"code": 0, "data": {"records": []}}, 200),
        ({"code": 0, "data": {"records": [{"id": "R-1"}]}}, 200),
        ({"code": 0, "data": {"records": []}}, 500),
    ],
)
def test_role_list_rejects_invalid_contract(payload: dict, status: int) -> None:
    with pytest.raises(AssertionError):
        RoleManagementPage._role_from_list_response(  # noqa: SLF001
            FakeResponse(payload, status)
        )


@pytest.mark.parametrize(
    "payload,status,valid",
    [
        ({"code": 0, "data": {}}, 200, True),
        ({"code": 200, "data": []}, 200, True),
        ({"code": 401, "msg": "令牌已失效"}, 200, False),
        ({"code": 0, "data": {}}, 500, False),
        ([], 200, False),
    ],
)
def test_role_response_requires_http_and_business_success(
    payload: object, status: int, valid: bool
) -> None:
    response = FakeResponse(payload, status)
    if valid:
        assert RoleManagementPage._validate_success_response(  # noqa: SLF001
            response, "数据权限"
        ) == payload
    else:
        with pytest.raises(AssertionError):
            RoleManagementPage._validate_success_response(  # noqa: SLF001
                response, "数据权限"
            )
