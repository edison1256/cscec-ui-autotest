"""Order query and history identity contract regression tests."""

from typing import Any

import pytest

from pages.console.console_workbench_page import WorkbenchListSnapshot
from pages.console.order_mgmt_page import OrderMgmtPage
from pages.console.resource_mgmt_page import PortalResourceRecord


class FakeResponse:
    """Minimal response without credentials or production data."""

    status = 200

    def __init__(self, payload: dict[str, Any], url: str = "https://example.test") -> None:
        self.payload = payload
        self.url = url

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


def portal_resource() -> PortalResourceRecord:
    """Return the synthetic cloud product selected before application."""
    return PortalResourceRecord(
        resource_id="RESOURCE-1",
        resource_type=2,
        name="CKafka消息队列",
        description="消息队列服务",
        app_name="云原生",
    )


@pytest.mark.parametrize(
    "url,valid",
    [
        (
            "https://cloud.example/#/subscription-process?resourceType=2&id=RESOURCE-1"
            "&specId=SPEC-1&packageId=PACKAGE-1&selectedSkuId=&buyMode=year&buyTime=1",
            True,
        ),
        ("https://cloud.example/#/service-center/2/RESOURCE-1", False),
        ("https://cloud.example/#/subscription-process", False),
    ],
)
def test_subscription_route_query(url: str, valid: bool) -> None:
    """Only the real subscription hash route may produce application identity."""
    if valid:
        query = OrderMgmtPage._subscription_route_query(url)
        assert query["id"] == ["RESOURCE-1"]
        assert query["selectedSkuId"] == [""]
    else:
        with pytest.raises(AssertionError):
            OrderMgmtPage._subscription_route_query(url)


@pytest.mark.parametrize(
    "code,data,resource_id,business_type,spec_id,valid",
    [
        (0, [{"node": "start"}], "RESOURCE-1", "10", "SPEC-1", True),
        (50000, [{"node": "start"}], "RESOURCE-1", "10", "SPEC-1", False),
        (0, [], "RESOURCE-1", "10", "SPEC-1", False),
        (0, [{"node": "start"}], "RESOURCE-2", "10", "SPEC-1", False),
        (0, [{"node": "start"}], "RESOURCE-1", "11", "SPEC-1", False),
        (0, [{"node": "start"}], "RESOURCE-1", "10", "SPEC-2", False),
    ],
)
def test_apply_flow_identity(
    code: int,
    data: list,
    resource_id: str,
    business_type: str,
    spec_id: str,
    valid: bool,
) -> None:
    """Apply-flow lookup must belong to the selected resource and spec."""
    url = (
        "https://cloud.example/flow?"
        f"resourceId={resource_id}&businessType={business_type}&specId={spec_id}"
    )
    response = FakeResponse({"code": code, "data": data}, url)
    if valid:
        assert OrderMgmtPage._validate_apply_flow_response(
            response, portal_resource(), "SPEC-1"
        ) == data
    else:
        with pytest.raises(AssertionError):
            OrderMgmtPage._validate_apply_flow_response(
                response, portal_resource(), "SPEC-1"
            )


@pytest.mark.parametrize(
    "code,resource_type,resource_id,draft_id,valid",
    [
        (0, "2", "RESOURCE-1", "", True),
        (50000, "2", "RESOURCE-1", "", False),
        (0, "1", "RESOURCE-1", "", False),
        (0, "2", "RESOURCE-2", "", False),
        (0, "2", "RESOURCE-1", "DRAFT-1", False),
    ],
)
def test_order_draft_lookup_is_readonly(
    code: int,
    resource_type: str,
    resource_id: str,
    draft_id: str,
    valid: bool,
) -> None:
    """Initial draft lookup must not target an existing draft or another resource."""
    url = (
        "https://cloud.example/draft?"
        f"resourceType={resource_type}&resourceId={resource_id}&id={draft_id}"
    )
    response = FakeResponse({"code": code}, url)
    if valid:
        assert OrderMgmtPage._validate_order_draft_response(
            response, portal_resource()
        ) is None
    else:
        with pytest.raises(AssertionError):
            OrderMgmtPage._validate_order_draft_response(
                response, portal_resource()
            )
