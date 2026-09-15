"""Unit tests for the API-backed console workbench snapshot."""

from __future__ import annotations

import pytest

from pages.console.console_workbench_page import ConsoleWorkbenchPage


class _FakeWorkbenchResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self.status = status
        self.url = (
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
