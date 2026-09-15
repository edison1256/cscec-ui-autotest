"""Unit tests for the API-backed console workbench snapshot."""

from __future__ import annotations

import pytest

from pages.console.console_workbench_page import ConsoleWorkbenchPage


class _FakeWorkbenchResponse:
    def __init__(
        self,
        payload: dict,
        status: int = 200,
        url: str | None = None,
    ) -> None:
        self.status = status
        self.url = url or (
            "https://irp.cscec.com/irp-api/irp-portal-console/"
            "workbench/overview/commonfunctions/list"
        )
        self._payload = payload

    def json(self) -> dict:
        return self._payload


def test_workbench_response_returns_configured_function_count() -> None:
    count = ConsoleWorkbenchPage._validate_configuration_response(  # noqa: SLF001
        _FakeWorkbenchResponse(
            {
                "code": 0,
                "data": [
                    {"functionName": "订单管理"},
                    {"functionName": "应用订阅"},
                ],
            }
        )
    )

    assert count == 2


def test_workbench_response_rejects_http_200_business_failure() -> None:
    with pytest.raises(AssertionError, match="业务失败"):
        ConsoleWorkbenchPage._validate_configuration_response(  # noqa: SLF001
            _FakeWorkbenchResponse(
                {"code": 50000, "message": "系统繁忙", "data": []}
            )
        )


def test_workbench_response_rejects_boolean_success_lookalike() -> None:
    with pytest.raises(AssertionError, match="业务失败"):
        ConsoleWorkbenchPage._validate_configuration_response(  # noqa: SLF001
            _FakeWorkbenchResponse({"code": False, "data": []})
        )


def test_list_response_preserves_first_business_record() -> None:
    snapshot = ConsoleWorkbenchPage._parse_list_response(  # noqa: SLF001
        _FakeWorkbenchResponse(
            {
                "code": 0,
                "data": {
                    "list": [
                        {
                            "id": "subscription-1",
                            "orderId": "order-1",
                            "rscName": "测试资源",
                        }
                    ],
                    "total": "1",
                },
            },
            url="https://irp.cscec.com/irp-api/example/list",
        ),
        "应用订阅",
    )

    assert snapshot.first_record["orderId"] == "order-1"
    assert ConsoleWorkbenchPage.detail_prerequisite(snapshot).satisfied


def test_empty_list_response_is_a_declared_prerequisite_miss() -> None:
    snapshot = ConsoleWorkbenchPage._parse_list_response(  # noqa: SLF001
        _FakeWorkbenchResponse(
            {"code": 0, "data": {"list": [], "total": "0"}},
            url="https://irp.cscec.com/irp-api/example/list",
        ),
        "组件订阅",
    )

    prerequisite = ConsoleWorkbenchPage.detail_prerequisite(snapshot)
    assert not prerequisite.satisfied
    assert prerequisite.actual == "records=0"


def test_detail_response_requires_the_selected_order_and_resource() -> None:
    ConsoleWorkbenchPage._validate_detail_response(  # noqa: SLF001
        _FakeWorkbenchResponse(
            {
                "code": 0,
                "data": {
                    "id": "order-1",
                    "resourceName": "测试资源",
                },
            },
            url=(
                "https://irp.cscec.com/irp-api/irp-portal-console/"
                "order/orderDetail?id=order-1"
            ),
        ),
        "order-1",
        "测试资源",
    )


def test_detail_response_rejects_a_different_business_object() -> None:
    with pytest.raises(AssertionError, match="错误业务对象"):
        ConsoleWorkbenchPage._validate_detail_response(  # noqa: SLF001
            _FakeWorkbenchResponse(
                {
                    "code": 0,
                    "data": {
                        "id": "order-2",
                        "resourceName": "测试资源",
                    },
                },
                url=(
                    "https://irp.cscec.com/irp-api/irp-portal-console/"
                    "order/orderDetail?id=order-2"
                ),
            ),
            "order-1",
            "测试资源",
        )
