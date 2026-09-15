"""Unit tests for strict data-resource list contracts."""

from __future__ import annotations

import pytest

from pages.console.resource_mgmt_page import ResourceMgmtPage


class _FakeResourceResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self.status = status
        self.url = (
            "https://irp.cscec.com/irp-api/irp-portal-console/"
            "data-resource/tableList"
        )
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def _record() -> dict[str, str]:
    return {
        "id": "2097154673008234497",
        "tableNameCn": "中建云测试专用",
        "tableNameEn": "cloudtest",
        "dataApplicationDomainName": "中建云测试专用",
        "dataApplicationName": "中建云测试专用",
        "l1Name": "中建云测试专用L1",
        "l2Name": "中建云测试专用L2",
        "l3Name": "中建云测试专用L3",
        "dataManageDepartment": "技术与大数据平台项目组",
        "systemProject": "技术与大数据平台项目组",
    }


def test_resource_list_response_preserves_business_identity() -> None:
    snapshot = ResourceMgmtPage._parse_list_response(  # noqa: SLF001
        _FakeResourceResponse(
            {
                "code": 0,
                "data": {"records": [_record()], "total": "1"},
            }
        )
    )

    assert snapshot.total == 1
    assert snapshot.first_record.table_name_en == "cloudtest"
    assert snapshot.first_record.l3_name == "中建云测试专用L3"


def test_resource_list_response_rejects_business_failure() -> None:
    with pytest.raises(AssertionError, match="业务失败"):
        ResourceMgmtPage._parse_list_response(  # noqa: SLF001
            _FakeResourceResponse(
                {
                    "code": 50000,
                    "message": "系统繁忙",
                    "data": {"records": [], "total": 0},
                }
            )
        )


def test_resource_list_response_requires_row_identity() -> None:
    record = _record()
    record["tableNameEn"] = ""

    with pytest.raises(AssertionError, match="tableNameEn"):
        ResourceMgmtPage._parse_list_response(  # noqa: SLF001
            _FakeResourceResponse(
                {
                    "code": 0,
                    "data": {"records": [record], "total": 1},
                }
            )
        )
