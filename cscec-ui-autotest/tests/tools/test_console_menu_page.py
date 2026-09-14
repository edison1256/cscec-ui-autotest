"""Unit tests for the API-backed console menu snapshot."""

from __future__ import annotations

import pytest

from pages.console.console_menu_page import ConsoleMenuPage


class _FakeMenuResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self.status = status
        self.url = "https://irp.cscec.com/engine/metadata/getMenuTreeForPortal"
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def test_menu_response_preserves_direct_child_contract() -> None:
    snapshot = ConsoleMenuPage._parse_menu_response(  # noqa: SLF001
        _FakeMenuResponse(
            {
                "code": 0,
                "data": [
                    {
                        "title": "权限管理",
                        "menuCode": "permission",
                        "disabled": False,
                        "forbid": False,
                        "children": [
                            {
                                "title": "角色管理",
                                "menuCode": "role",
                                "children": [],
                            }
                        ],
                    }
                ],
            }
        )
    )

    permission = snapshot.top_level("权限管理")
    assert permission is not None
    assert permission.available
    assert [child.title for child in permission.children] == ["角色管理"]


def test_menu_response_rejects_http_200_business_failure() -> None:
    with pytest.raises(AssertionError, match="业务失败"):
        ConsoleMenuPage._parse_menu_response(  # noqa: SLF001
            _FakeMenuResponse({"code": 50000, "message": "系统繁忙", "data": []})
        )


def test_menu_response_rejects_boolean_success_lookalike() -> None:
    with pytest.raises(AssertionError, match="业务失败"):
        ConsoleMenuPage._parse_menu_response(  # noqa: SLF001
            _FakeMenuResponse({"code": False, "data": []})
        )
