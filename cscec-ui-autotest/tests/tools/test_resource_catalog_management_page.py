"""Unit contracts for resource-catalog list and detail responses."""

from __future__ import annotations

import pytest

from pages.console.resource_catalog_management_page import (
    CatalogRecord,
    ResourceCatalogManagementPage,
)


class _Response:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._payload = payload
        self.status = status

    def json(self) -> dict:
        return self._payload


def test_catalog_record_preserves_list_identity() -> None:
    record = ResourceCatalogManagementPage._record_from_response(  # noqa: SLF001
        _Response(
            {
                "code": 0,
                "data": {
                    "list": [
                        {
                            "id": "APP-1",
                            "appName": "测试应用",
                            "productCode": "APP-CODE-1",
                        }
                    ]
                },
            }
        ),
        label="应用管理",
        name_fields=("appName",),
        code_fields=("productCode",),
    )

    assert record == CatalogRecord("APP-1", "测试应用", "APP-CODE-1")


@pytest.mark.parametrize(
    "response",
    [
        _Response({"code": 50000, "message": "系统繁忙", "data": {}}),
        _Response({"code": 0, "data": {"list": []}}),
        _Response({"code": 0, "data": {"list": [{"id": "APP-1"}]}}),
    ],
)
def test_catalog_record_rejects_invalid_list_contract(response: _Response) -> None:
    with pytest.raises(AssertionError):
        ResourceCatalogManagementPage._record_from_response(  # noqa: SLF001
            response,
            label="应用管理",
            name_fields=("appName",),
            code_fields=("productCode",),
        )


def test_application_detail_must_match_selected_record() -> None:
    selected = CatalogRecord("APP-1", "测试应用", "APP-CODE-1")
    mismatched = _Response(
        {"code": 0, "data": {"id": "APP-2", "appName": "其他应用"}}
    )

    with pytest.raises(AssertionError, match="其他业务对象"):
        ResourceCatalogManagementPage._assert_detail_identity(  # noqa: SLF001
            mismatched,
            selected,
            "应用详情",
        )
