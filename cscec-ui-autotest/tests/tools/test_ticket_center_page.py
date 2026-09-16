"""Ticket list, query, detail and process identity contract tests."""

from __future__ import annotations

from typing import Any

import pytest

from pages.console.ticket_center_page import (
    TicketCenterPage,
    TicketListSnapshot,
    TicketRecord,
)


class FakeRequest:
    """Minimal request carrying a synthetic JSON body."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.post_data_json = payload


class FakeResponse:
    """Minimal response without credentials or production data."""

    def __init__(
        self,
        payload: dict[str, Any],
        *,
        status: int = 200,
        request: dict[str, Any] | None = None,
    ) -> None:
        self.payload = payload
        self.status = status
        self.request = FakeRequest(request or {})

    def json(self) -> dict[str, Any]:
        """Return the synthetic business response."""
        return self.payload


def ticket_raw(**overrides: Any) -> dict[str, Any]:
    """Build one complete synthetic ticket row."""
    row = {
        "id": "1",
        "workOrderCode": "WO-1",
        "title": "测试工单",
        "workOrderDescription": "测试描述",
        "workOrderTypeDesc": "咨询",
        "creatorName": "创建人",
        "assigneeName": "处理人",
        "insertDt": "2026-09-16 10:00:00",
    }
    row.update(overrides)
    return row


def ticket_record() -> TicketRecord:
    """Build the typed identity expected by validators."""
    return TicketCenterPage._parse_ticket_record(ticket_raw())


@pytest.mark.parametrize(
    "payload,status,valid",
    [
        ({"code": 0, "data": {"records": [ticket_raw()], "total": "1"}}, 200, True),
        ({"code": 50000, "data": {"records": [], "total": 0}}, 200, False),
        ({"code": 0, "data": {"records": None, "total": 0}}, 200, False),
        ({"code": 0, "data": {"records": [ticket_raw()], "total": 0}}, 200, False),
        ({"code": 0, "data": {"records": [], "total": "bad"}}, 200, False),
        ({"code": 0, "data": {"records": [], "total": 0}}, 500, False),
    ],
)
def test_ticket_list_contract(payload: dict, status: int, valid: bool) -> None:
    """Reject transport, envelope and pagination inconsistencies."""
    response = FakeResponse(payload, status=status)
    if valid:
        result = TicketCenterPage._parse_list_response(response)
        assert result.first_record.code == "WO-1"
    else:
        with pytest.raises(AssertionError):
            TicketCenterPage._parse_list_response(response)


def test_ticket_record_requires_identity_fields() -> None:
    """A row missing a field used by the detail proof is not a valid sample."""
    with pytest.raises(AssertionError, match="assignee_name"):
        TicketCenterPage._parse_ticket_record(ticket_raw(assigneeName=""))


@pytest.mark.parametrize(
    "query,records,valid",
    [
        ({"workOrderCode": "WO-1"}, [ticket_record()], True),
        ({}, [ticket_record()], False),
        ({"workOrderCode": "WO-1"}, [], False),
        ({"workOrderCode": "WO-1"}, [TicketCenterPage._parse_ticket_record(ticket_raw(id="2"))], False),
        ({"workOrderCode": "WO-1"}, [TicketCenterPage._parse_ticket_record(ticket_raw(workOrderCode="WO-2"))], False),
    ],
)
def test_ticket_query_identity(
    query: dict,
    records: list[TicketRecord],
    valid: bool,
) -> None:
    """Only the submitted code and original ticket may pass."""
    snapshot = TicketListSnapshot(tuple(records), len(records))
    if valid:
        TicketCenterPage._validate_query_result(
            {"queryfilter": query}, snapshot, ticket_record()
        )
    else:
        with pytest.raises(AssertionError):
            TicketCenterPage._validate_query_result(
                {"queryfilter": query}, snapshot, ticket_record()
            )


@pytest.mark.parametrize(
    "code,data,valid",
    [
        (0, ticket_raw(), True),
        (50000, ticket_raw(), False),
        (0, ticket_raw(id="2"), False),
        (0, ticket_raw(workOrderCode="WO-2"), False),
        (0, ticket_raw(title="其他标题"), False),
        (0, ticket_raw(workOrderDescription="其他描述"), False),
    ],
)
def test_ticket_detail_identity(code: Any, data: dict, valid: bool) -> None:
    """Business failures and unrelated ticket details must fail."""
    response = FakeResponse({"code": code, "data": data})
    if valid:
        assert TicketCenterPage._validate_detail_response(response, ticket_record()) == data
    else:
        with pytest.raises(AssertionError):
            TicketCenterPage._validate_detail_response(response, ticket_record())


@pytest.mark.parametrize(
    "request_body,code,data,valid",
    [
        ({"queryfilter": {"workOrderId": "1"}}, 0, {"records": [], "total": 0}, True),
        ({"queryfilter": {"workOrderId": "2"}}, 0, {"records": [], "total": 0}, False),
        ({"queryfilter": {"workOrderId": "1"}}, 50000, {"records": []}, False),
        ({"queryfilter": {"workOrderId": "1"}}, 0, {"records": None}, False),
    ],
)
def test_ticket_process_identity(
    request_body: dict,
    code: Any,
    data: dict,
    valid: bool,
) -> None:
    """Process history must be requested for the selected ticket."""
    response = FakeResponse({"code": code, "data": data}, request=request_body)
    if valid:
        assert TicketCenterPage._validate_process_response(response, "1") == []
    else:
        with pytest.raises(AssertionError):
            TicketCenterPage._validate_process_response(response, "1")
