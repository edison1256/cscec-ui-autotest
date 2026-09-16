"""Approval-list business contract regression tests."""

from typing import Any

import pytest

from pages.console.approval_center_page import ApprovalCenterPage


class FakeRequest:
    """Minimal request body used by a synthetic response."""

    def __init__(self, body: Any) -> None:
        self.post_data_json = body


class FakeResponse:
    """Minimal Playwright response contract without production data."""

    def __init__(
        self,
        payload: Any,
        *,
        request_body: Any = None,
        status: int = 200,
    ) -> None:
        self.status = status
        self.request = FakeRequest(request_body)
        self._payload = payload

    def json(self) -> Any:
        """Return the synthetic JSON payload."""
        return self._payload


def _record(**overrides: Any) -> dict[str, Any]:
    record = {
        "procInstId": "PROC-1",
        "procName": "测试流程",
        "description": "测试描述",
        "bizName": "流程",
        "bizCode": "flowmodel",
        "bizKey": "BIZ-1",
        "startUserName": "测试用户",
        "startUserDeptName": "测试部门",
        "processStateName": "结束",
    }
    record.update(overrides)
    return record


def _response(
    *,
    status_filter: Any = 1,
    code: Any = 0,
    records: Any = None,
    total: Any = "1",
    http_status: int = 200,
) -> FakeResponse:
    if records is None:
        records = [_record()]
    return FakeResponse(
        {"code": code, "data": {"list": records, "total": total}},
        request_body={"status": status_filter},
        status=http_status,
    )


def test_approval_list_preserves_business_identity() -> None:
    """A valid completed record keeps its process and business identities."""
    snapshot = ApprovalCenterPage._parse_list_response(
        _response(),
        expected_status=1,
    )

    assert snapshot.total == 1
    assert snapshot.first_record.proc_inst_id == "PROC-1"
    assert snapshot.first_record.biz_key == "BIZ-1"


@pytest.mark.parametrize(
    "response,match",
    [
        (_response(http_status=500), "HTTP"),
        (_response(code=50000), "业务失败"),
        (_response(code=False), "业务失败"),
        (_response(status_filter=0), "请求状态错误"),
        (_response(records={}), "data.list"),
        (_response(total="invalid"), "total"),
        (_response(total=0), "total 小于"),
    ],
)
def test_approval_list_rejects_invalid_contract(
    response: FakeResponse,
    match: str,
) -> None:
    """Transport, business, status and structure failures stay blocking."""
    with pytest.raises(AssertionError, match=match):
        ApprovalCenterPage._parse_list_response(response, expected_status=1)


@pytest.mark.parametrize("field", ["procInstId", "procName", "bizCode", "bizKey"])
def test_approval_record_requires_navigation_identity(field: str) -> None:
    """A record cannot drive a detail action without its route identity."""
    with pytest.raises(AssertionError, match=field):
        ApprovalCenterPage._parse_list_response(
            _response(records=[_record(**{field: ""})]),
            expected_status=1,
        )


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        (
            "https://irp.cscec.com/udpweb/portal/index.html"
            "#/sub/resource/flowmodel/detail?wfpiid=PROC-1&id=BIZ-1",
            {"wfpiid": ["PROC-1"], "id": ["BIZ-1"]},
        ),
        (
            "https://irp.cscec.com/sub/workflow/flowdetail?procInstId=PROC-2",
            {"procInstId": ["PROC-2"]},
        ),
    ],
)
def test_route_query_supports_hash_and_standard_routes(
    url: str,
    expected: dict[str, list[str]],
) -> None:
    assert ApprovalCenterPage._route_query(url) == expected
