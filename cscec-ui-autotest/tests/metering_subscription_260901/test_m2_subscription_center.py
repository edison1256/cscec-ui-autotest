"""M2: 工作台订阅中心 API 列表（F01，P0）— 名义编号对齐版.

PRE verified 2026-10-09: 当前账号（普通成员）工作台菜单树无“订阅中心”节点。
M2 全模块被入口阻塞；已实现用例为入口探测，其余按大纲名义编号标注
ROLE_REQUIRED（待管理员账号复核）。
"""

from __future__ import annotations

import pytest

from tests.metering_subscription_260901.helpers import (
    WORKBENCH_URL,
    click_when_visible,
    visible_texts,
)

pytestmark = [pytest.mark.readonly, pytest.mark.portal]

ENTRY_SKIP = (
    "ROLE_REQUIRED: 当前账号工作台无“订阅中心”菜单（M2 模块前置入口缺失，"
    "等价行为已在本租户“我的订阅-API订阅”视图验证，见 M3/M4 对应项）；"
    "需租户管理员/租户运营账号复核"
)


def _skip_if_no_entry(wb_page) -> None:
    wb_page.goto("about:blank", wait_until="domcontentloaded", timeout=30000)
    wb_page.goto(WORKBENCH_URL, wait_until="domcontentloaded", timeout=60000)
    wb_page.wait_for_load_state("networkidle", timeout=20000)
    body = visible_texts(wb_page)
    if "订阅中心" not in body:
        pytest.skip(ENTRY_SKIP)
    pytest.fail(
        "订阅中心入口已可见：本用例尚未实现管理员视角断言，"
        "请按大纲补全后再执行（防假通过保护）"
    )


class TestM2DefaultLoad:
    """M2.1 默认加载与列表字段."""

    def test_m2_1_1__subscription_center_load(self, wb_page):
        """主流程：租户管理员进入订阅中心-API列表，父子表初始折叠."""
        _skip_if_no_entry(wb_page)
        assert click_when_visible(wb_page, "订阅中心", timeout_ms=5000)

    def test_m2_1_2__parent_headers(self, wb_page):
        """UI：父表列名依次为资源名称/资源编码/服务模式/资源所属方/订阅数量/操作."""
        _skip_if_no_entry(wb_page)

    def test_m2_1_3__wps_rows_by_service_mode(self, wb_page):
        """数据：WPS 服务组件按不同服务模式分别成行."""
        _skip_if_no_entry(wb_page)

    def test_m2_1_4__api_resource_identification(self, wb_page):
        """数据：API 资源名称（wdl集成平台组件）查询进入 API 列表口径."""
        _skip_if_no_entry(wb_page)

    def test_m2_1_5__sdk_not_in_list(self, wb_page):
        """数据：SDK 资源（WPS服务）不混入 API 权益聚合列表."""
        _skip_if_no_entry(wb_page)

    def test_m2_1_6__no_service_mode_missing(self, wb_page):
        """展示：不存在服务模式缺失的 API 类组件时（空态/正常态展示）."""
        _skip_if_no_entry(wb_page)


class TestM2Query:
    """M2.2 查询条件."""

    def test_m2_2_1__query_by_code(self, wb_page):
        """查询：输入存在的资源编码查询."""
        _skip_if_no_entry(wb_page)

    def test_m2_2_2__query_by_name(self, wb_page):
        """查询：输入存在的资源名称（WPS服务组件）查询."""
        _skip_if_no_entry(wb_page)

    def test_m2_2_3__combined_query(self, wb_page):
        """查询：资源编码+资源名称组合查询."""
        _skip_if_no_entry(wb_page)

    def test_m2_2_4__reset(self, wb_page):
        """重置：修改条件后重置恢复默认并重新加载."""
        _skip_if_no_entry(wb_page)

    def test_m2_2_5__empty_result(self, wb_page):
        """空结果：输入不存在的资源编码查询列表为空."""
        _skip_if_no_entry(wb_page)


class TestM2StatisticsScope:
    """M2.3 统计方式与租户范围."""

    def test_m2_3_1__aggregate_scope(self, wb_page):
        """数据范围：汇总本租户及下级数据."""
        _skip_if_no_entry(wb_page)

    def test_m2_3_2__scope_only_self(self, wb_page):
        """数据范围：仅本租户."""
        _skip_if_no_entry(wb_page)

    def test_m2_3_3__scope_switch_consistency(self, wb_page):
        """一致性：切换统计方式父表数量与子表范围同步变化."""
        _skip_if_no_entry(wb_page)

    def test_m2_3_4__no_child_tenant_boundary(self, wb_page):
        """边界：无下级租户时汇总结果与仅本租户一致."""
        _skip_if_no_entry(wb_page)


class TestM2Aggregation:
    """M2.4 订阅数量聚合口径."""

    def test_m2_4_1__dedup_by_entitlement(self, wb_page):
        """数据：多成功订单按权益账户去重（非订单数累加）."""
        _skip_if_no_entry(wb_page)

    def test_m2_4_2__per_app_counter(self, wb_page):
        """数据：不同应用订阅同服务模式分别计数."""
        _skip_if_no_entry(wb_page)

    def test_m2_4_3__per_service_mode(self, wb_page):
        """数据：同一资源多服务模式独立展示订阅数量."""
        _skip_if_no_entry(wb_page)

    def test_m2_4_4__multi_api_one_account(self, wb_page):
        """数据：同一权益账户多 API 订阅数量仍计 1."""
        _skip_if_no_entry(wb_page)


class TestM2ExpandCollapse:
    """M2.5 折叠与展开."""

    def test_m2_5_1__expand_single_row(self, wb_page):
        """交互：点击父行查看，仅当前行展开且按钮变收起."""
        _skip_if_no_entry(wb_page)

    def test_m2_5_2__collapse_restores(self, wb_page):
        """交互：再次点击收起，子表关闭按钮恢复查看（等价行为见 M3.5.3）."""
        _skip_if_no_entry(wb_page)

    def test_m2_5_3__switch_row_expand(self, wb_page):
        """交互：展开第一行后点第二行查看，单行展开状态符合约定."""
        _skip_if_no_entry(wb_page)

    def test_m2_5_4__initial_collapsed_on_reentry(self, wb_page):
        """状态：重新进入页面父子表恢复初始折叠."""
        _skip_if_no_entry(wb_page)
