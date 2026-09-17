"""Unit tests for strict data-resource list contracts."""

from __future__ import annotations

import pytest

from pages.console.resource_mgmt_page import (
    PortalResourceSearchSnapshot,
    ResourceMgmtPage,
)


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


def _portal_record() -> dict:
    return {
        "id": "RESOURCE-1",
        "resourceType": 2,
        "name": "CKafka消息队列",
        "description": "消息队列服务",
        "appName": "云原生",
    }


def test_portal_search_response_preserves_resource_identity() -> None:
    snapshot = ResourceMgmtPage._parse_portal_search_response(  # noqa: SLF001
        _FakeResourceResponse(
            {"code": 0, "data": {"list": [_portal_record()], "total": "1"}}
        )
    )

    assert snapshot.total == 1
    assert snapshot.first_record.resource_id == "RESOURCE-1"
    assert snapshot.first_record.resource_type == 2


@pytest.mark.parametrize(
    "payload",
    [
        {"code": 50000, "data": {"list": [], "total": 0}},
        {"code": 0, "data": {"list": None, "total": 0}},
        {"code": 0, "data": {"list": [_portal_record()], "total": 0}},
        {"code": 0, "data": {"list": [], "total": "bad"}},
    ],
)
def test_portal_search_response_rejects_invalid_contract(payload: dict) -> None:
    with pytest.raises(AssertionError):
        ResourceMgmtPage._parse_portal_search_response(  # noqa: SLF001
            _FakeResourceResponse(payload)
        )


@pytest.mark.parametrize(
    "query,records,valid",
    [
        ({"resourceType": "2", "keyword": "CKafka消息队列"}, [_portal_record()], True),
        ({"resourceType": "1", "keyword": "CKafka消息队列"}, [_portal_record()], False),
        ({"resourceType": "2", "keyword": "其他"}, [_portal_record()], False),
        ({"resourceType": "2", "keyword": "CKafka消息队列"}, [], False),
    ],
)
def test_portal_search_request_and_identity(
    query: dict,
    records: list[dict],
    valid: bool,
) -> None:
    snapshot = PortalResourceSearchSnapshot(
        tuple(ResourceMgmtPage._parse_portal_resource(row) for row in records),  # noqa: SLF001
        len(records),
    )
    action = lambda: ResourceMgmtPage._validate_portal_search_request(  # noqa: E731, SLF001
        {"queryfilter": query}, snapshot, "CKafka消息队列"
    )
    if valid:
        action()
    else:
        with pytest.raises(AssertionError):
            action()


@pytest.mark.parametrize(
    "code,data,valid",
    [
        (0, _portal_record(), True),
        (50000, _portal_record(), False),
        (0, {**_portal_record(), "id": "RESOURCE-2"}, False),
        (0, {**_portal_record(), "resourceType": 1}, False),
        (0, {**_portal_record(), "name": "其他"}, False),
        (0, {**_portal_record(), "description": "其他描述"}, False),
    ],
)
def test_portal_detail_matches_searched_resource(
    code: int,
    data: dict,
    valid: bool,
) -> None:
    expected = ResourceMgmtPage._parse_portal_resource(_portal_record())  # noqa: SLF001
    response = _FakeResourceResponse({"code": code, "data": data})
    if valid:
        assert ResourceMgmtPage._validate_portal_detail_response(  # noqa: SLF001
            response, expected
        ) == data
    else:
        with pytest.raises(AssertionError):
            ResourceMgmtPage._validate_portal_detail_response(  # noqa: SLF001
                response, expected
            )
