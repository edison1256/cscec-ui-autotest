"""Order query and history identity contract regression tests."""

from typing import Any

import pytest

from pages.console.console_workbench_page import WorkbenchListSnapshot
from pages.console.order_mgmt_page import OrderMgmtPage


class FakeResponse:
    """Minimal response without credentials or production data."""

    status = 200

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def json(self) -> dict[str, Any]:
        """Return a synthetic business response."""
        return self.payload


@pytest.mark.parametrize(
    "query,records,valid",
    [
        ({"orderCode": "TEST-1"}, [{"id": "1", "orderCode": "TEST-1"}], True),
        ({}, [{"id": "1", "orderCode": "TEST-1"}], False),
        ({"orderCode": "TEST-1"}, [], False),
        ({"orderCode": "TEST-1"}, [{"id": "2", "orderCode": "TEST-1"}], False),
        ({"orderCode": "TEST-1"}, [{"id": "1", "orderCode": "OTHER"}], False),
    ],
)
def test_order_query_identity(query: dict, records: list, valid: bool) -> None:
    """Only the submitted code and the original order may pass."""
    snapshot = WorkbenchListSnapshot(
        "orders",
        "https://example.test/order/page",
        tuple(records),
    )
    expected = {"id": "1", "orderCode": "TEST-1"}
    if valid:
        OrderMgmtPage._validate_query_result({"queryfilter": query}, snapshot, expected)
    else:
        with pytest.raises(AssertionError):
            OrderMgmtPage._validate_query_result({"queryfilter": query}, snapshot, expected)


@pytest.mark.parametrize(
    "code,data,valid",
    [
        (0, {"orderId": "1", "orderChangeList": [{"orderId": "1"}]}, True),
        (0, {"orderId": "1", "orderChangeList": []}, True),
        (50000, {"orderId": "1", "orderChangeList": []}, False),
        (False, {"orderId": "1", "orderChangeList": []}, False),
        (0, {"orderId": "2", "orderChangeList": []}, False),
        (0, {"orderId": "1", "orderChangeList": [{"orderId": "2"}]}, False),
        (0, {"orderId": "1", "orderChangeList": None}, False),
    ],
)
def test_order_history_identity(code: Any, data: dict, valid: bool) -> None:
    """Business failures and unrelated order histories must fail."""
    response = FakeResponse({"code": code, "data": data})
    if valid:
        assert OrderMgmtPage._validate_history(response, "1") == data["orderChangeList"]
    else:
        with pytest.raises(AssertionError):
            OrderMgmtPage._validate_history(response, "1")
