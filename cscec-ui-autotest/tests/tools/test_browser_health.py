"""Unit tests for browser and business-response health monitoring."""

from __future__ import annotations

import pytest

from core.browser_health import BrowserHealthMonitor, BusinessResponseRule


class _FakeContext:
    pages = []


class _FakePage:
    context = _FakeContext()


class _FakeRequest:
    resource_type = "xhr"


class _FakeResponse:
    def __init__(self, url: str, payload: dict, status: int = 200) -> None:
        self.url = url
        self.status = status
        self.request = _FakeRequest()
        self._payload = payload

    def header_value(self, name: str) -> str:
        assert name == "content-type"
        return "application/json"

    def json(self) -> dict:
        return self._payload


def test_http_200_business_failure_is_rejected() -> None:
    monitor = BrowserHealthMonitor(
        _FakePage(),
        "组织树加载",
        business_rules=(BusinessResponseRule(r"/getLazyLoadOrgTree"),),
    )

    monitor._on_response(  # noqa: SLF001 - focused unit coverage of event callback
        _FakeResponse(
            "https://cloud.cscec.com/basedata/org/getLazyLoadOrgTree",
            {"code": 50000, "message": "系统繁忙，请稍后再试"},
        )
    )

    with pytest.raises(AssertionError, match="business_response"):
        monitor.assert_healthy()


def test_successful_declared_business_response_passes() -> None:
    monitor = BrowserHealthMonitor(
        _FakePage(),
        "角色权限树加载",
        business_rules=(BusinessResponseRule(r"/getPermissionTree"),),
    )

    monitor._on_response(  # noqa: SLF001 - focused unit coverage of event callback
        _FakeResponse(
            "https://irp.cscec.com/tenant-role/getPermissionTree",
            {"code": 0, "message": "操作成功", "data": []},
        )
    )

    monitor.assert_healthy()


def test_missing_declared_business_response_is_rejected() -> None:
    monitor = BrowserHealthMonitor(
        _FakePage(),
        "订单管理页面",
        business_rules=(BusinessResponseRule(r"/order/page"),),
    )

    with pytest.raises(AssertionError, match="business_response_missing"):
        monitor.assert_healthy()
