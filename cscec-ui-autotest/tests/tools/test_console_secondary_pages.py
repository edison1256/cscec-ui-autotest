"""Unit contracts for Batch D secondary console pages."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from pages.console.console_menu_page import ConsoleMenuNode, ConsoleMenuSnapshot
from pages.console.evaluation_management_page import (
    EvaluationManagementPage,
    EvaluationTemplateRecord,
)
from pages.console.metering_statistics_page import (
    MeteringStatisticsPage,
    TenantOverviewRecord,
)
from pages.console.system_configuration_page import (
    SystemConfigurationPage,
    SystemListRecord,
)


@dataclass
class FakeResponse:
    """Minimal response accepted by the page-level parsers."""

    payload: object
    status: int = 200

    def json(self) -> object:
        return self.payload


def test_nested_menu_path_resolves_exact_nodes() -> None:
    leaf = ConsoleMenuNode("首页配置", "3", (), False, False)
    group = ConsoleMenuNode("门户管理", "2", (leaf,), False, False)
    root = ConsoleMenuNode("系统配置", "1", (group,), False, False)
    snapshot = ConsoleMenuSnapshot((root,))
    assert snapshot.path("系统配置", "门户管理", "首页配置") == (root, group, leaf)
    assert snapshot.path("系统配置", "门户管理", "不存在") is None


def test_evaluation_record_preserves_dynamic_identity() -> None:
    response = FakeResponse(
        {"code": 0, "data": {"records": [{"id": "T-1", "assessmentName": "空间评价"}]}}
    )
    assert EvaluationManagementPage._record_from_response(response) == (  # noqa: SLF001
        EvaluationTemplateRecord("T-1", "空间评价")
    )


def test_system_records_support_banner_and_audit_shapes() -> None:
    banner = FakeResponse(
        {"code": 0, "data": {"list": [{"bannerId": "B-1", "bannerName": "首页"}]}}
    )
    assert SystemConfigurationPage._record_from_response(  # noqa: SLF001
        banner,
        "首页配置",
        id_fields=("id", "bannerId"),
        name_fields=("bannerName", "name"),
    ) == SystemListRecord("B-1", "首页")

    audit = FakeResponse(
        {"code": 200, "data": {"records": [{"id": 9, "creatorName": "测试用户"}]}}
    )
    assert SystemConfigurationPage._record_from_response(  # noqa: SLF001
        audit,
        "日志审计",
        id_fields=("id",),
        name_fields=("creatorName",),
    ) == SystemListRecord("9", "测试用户")


@pytest.mark.parametrize(
    "payload,id_fields,name_fields,expected",
    [
        (
            {"code": 0, "data": [{"id": "C-1", "name": "云资源"}]},
            ("id",),
            ("name",),
            SystemListRecord("C-1", "云资源"),
        ),
        (
            {"code": 0, "data": [{"id": "S-1", "categoryName": "硬件"}]},
            ("id",),
            ("categoryName",),
            SystemListRecord("S-1", "硬件"),
        ),
        (
            {"code": 0, "data": [{"id": "L-1", "name": "辅助决策"}]},
            ("id",),
            ("name",),
            SystemListRecord("L-1", "辅助决策"),
        ),
        (
            {
                "code": 0,
                "data": {
                    "list": [{"id": "M-1", "manufacturerName": "测试厂商"}]
                },
            },
            ("id",),
            ("manufacturerName",),
            SystemListRecord("M-1", "测试厂商"),
        ),
    ],
)
def test_system_resource_records_preserve_visible_identity(
    payload, id_fields, name_fields, expected
) -> None:
    assert SystemConfigurationPage._record_from_response(  # noqa: SLF001
        FakeResponse(payload),
        "系统配置",
        id_fields=id_fields,
        name_fields=name_fields,
    ) == expected


def test_metering_record_preserves_tenant_identity() -> None:
    response = FakeResponse(
        {
            "code": 0,
            "data": {
                "records": [
                    {"tenantNo": "ZH_01_0000", "tenantName": "中建云"}
                ]
            },
        }
    )
    assert MeteringStatisticsPage._record_from_response(  # noqa: SLF001
        response, "资源概览"
    ) == TenantOverviewRecord("ZH_01_0000", "中建云")


@pytest.mark.parametrize(
    "parser,response",
    [
        (
            lambda response: EvaluationManagementPage._record_from_response(response),
            FakeResponse({"code": 50000, "data": {}}),
        ),
        (
            lambda response: MeteringStatisticsPage._record_from_response(response, "资源概览"),
            FakeResponse({"code": 0, "data": {"records": []}}),
        ),
        (
            lambda response: SystemConfigurationPage._record_from_response(
                response,
                "日志审计",
                id_fields=("id",),
                name_fields=("creatorName",),
            ),
            FakeResponse({"code": 0, "data": {"records": [{}]}}),
        ),
    ],
)
def test_secondary_page_contracts_reject_invalid_payloads(parser, response) -> None:
    with pytest.raises(AssertionError):
        parser(response)
