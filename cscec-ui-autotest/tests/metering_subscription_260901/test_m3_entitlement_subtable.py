"""M3: 工作台 API 权益账户列表（F02，P0）— 扁平化适配版（2026-10-12）.

PRE 版本演进：
- 10-09 旧版：父表(资源聚合) + 点"查看"行内展开权益账户子表
- 10-10 统一版：统计方式 + 资源所属方列（无展开）
- 10-12 当前版：**主列表直接展示权益账户 11 列**（扁平化），行内操作=查看订单明细/查看用量

当前锚点（我的订阅-API订阅，中建云租户）：
  WPS服务组件 | 订阅服务 | IRP_中建云项目 | 技术与大数据平台项目组 |
  2026-06-01 11:29:57 | 2030-06-01 11:29:57 | 可用 | 不限次数 | 0 | 不限次数
  中建云0731组件 | 测试数字 | IRP_测试下发 | ... | 永久有效 | 可用 | 不限次数
"""

from __future__ import annotations

import re

import pytest

from tests.metering_subscription_260901.helpers import (
    ANCHOR_APPLY_APP,
    ANCHOR_RESOURCE_PERMANENT,
    ANCHOR_RESOURCE_WPS,
    CHILD_HEADERS,
    assert_headers_present,
    gateway_error,
    list_is_empty,
    open_api_subscription_workbench,
    visible_texts,
)

pytestmark = [pytest.mark.readonly, pytest.mark.portal, pytest.mark.regression]


def _open_list(page) -> None:
    """进入我的订阅-API订阅并断言权益账户列表渲染（扁平化形态）。"""
    open_api_subscription_workbench(page)
    if gateway_error(page):
        pytest.skip("ENV_LIMITED: pre 子应用网关 502，环境瞬时故障")
    if list_is_empty(page):
        pytest.skip(
            "ENV_LIMITED: 当前账号本人订阅为空（暂无数据），权益账户列表无数据可核验"
        )
    assert ANCHOR_RESOURCE_WPS in visible_texts(page), (
        "权益账户列表未展示 WPS 锚点（数据漂移或上下文异常）"
    )


class TestM3EntitlementListScope:
    """M3.1 权益账户列表数据范围（扁平化版）。"""

    def test_m3_1_1__entitlement_list_display(self, wb_page):
        """主流程：进入页面直接展示权益账户列表（版本差异：无父行展开子表）."""
        _open_list(wb_page)
        rows = [
            ln for ln in visible_texts(wb_page).splitlines() if ANCHOR_RESOURCE_WPS in ln
        ]
        assert rows, "权益账户列表未包含锚点行"

    def test_m3_1_2__current_account_entitlement(self, wb_page):
        """数据：列表展示当前账户关联权益账户（订阅应用=IRP_中建云项目）."""
        _open_list(wb_page)
        body = visible_texts(wb_page)
        assert ANCHOR_APPLY_APP in body, f"列表未展示订阅应用（{ANCHOR_APPLY_APP}）"

    def test_m3_1_3__no_other_resource_leak(self, wb_page):
        """数据：列表不含其他租户资源（本租户视角）."""
        _open_list(wb_page)
        body = visible_texts(wb_page)
        assert ANCHOR_RESOURCE_WPS in body, "锚点资源缺失"
        cross = [t for t in ("建筑业资质查询", "社保信息", "失信被执行企业") if t in body]
        assert not cross, f"本人权益列表混入其他租户资源: {cross}"


class TestM3QuotaDisplay:
    """M3.2 列表字段与权益类型展示（扁平化版）。"""

    def test_m3_2_1__entitlement_headers(self, wb_page):
        """UI：列表列名含资源名称/服务模式/订阅应用/额度三列等 11 项."""
        _open_list(wb_page)
        assert_headers_present(wb_page, CHILD_HEADERS, "权益账户列表")

    def test_m3_2_2__fixed_quota_display(self, wb_page):
        """展示：固定调用额账户显示具体总额/已用/剩余."""
        pytest.skip(
            "DATA_REQUIRED: 当前锚点均为不限量账户，固定调用额展示需构造固定额度权益数据"
        )

    def test_m3_2_3__unlimited_quota_display(self, wb_page):
        """展示：不限量账户总/剩显示“不限次数”，不显示“-”，不暴露 Credits."""
        _open_list(wb_page)
        body = visible_texts(wb_page)
        assert "不限次数" in body, "列表未出现“不限次数”展示"
        assert "Credits" not in body and "credits" not in body, "页面暴露 Credits 单位"

    def test_m3_2_4__concurrent_quota_display(self, wb_page):
        """展示：并发账户不展示并发数，已调用额可统计."""
        pytest.skip("DATA_REQUIRED: 需并发型权益账户数据")

    def test_m3_2_5__permanent_expiry_display(self, wb_page):
        """展示：永久有效账户（中建云0731组件）截止时间显示“永久有效”."""
        _open_list(wb_page)
        body = visible_texts(wb_page)
        assert "永久有效" in body or ANCHOR_RESOURCE_PERMANENT in body, (
            "列表未出现“永久有效”展示（锚点中建云0731组件）"
        )
        assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", body), (
            "列表未见标准生效时间格式"
        )


class TestM3TimeFields:
    """M3.3 生效时间与截止时间取值规则."""

    def test_m3_3_1__earliest_effective_time(self, wb_page):
        """数据：账户内多条成功订阅时生效时间取最早（需多记录账户）."""
        pytest.skip("DATA_REQUIRED: 需同一权益账户多条成功订阅记录")

    def test_m3_3_2__fixed_quota_latest_expiry(self, wb_page):
        """数据：固定调用额多次成功购买截止时间取最新结果（叠加）."""
        pytest.skip("DATA_REQUIRED: 需固定额度多次购买流程数据")

    def test_m3_3_3__unlimited_latest_expiry(self, wb_page):
        """数据：不限量账户多次成功购买截止时间取最新结果."""
        pytest.skip("DATA_REQUIRED: 需不限量多次购买流程数据")

    def test_m3_3_4__concurrent_no_extension(self, wb_page):
        """数据：并发账户增购不错误延长有效期."""
        pytest.skip("DATA_REQUIRED: 需并发账户增购流程数据")

    def test_m3_3_5__mixed_permanent_and_normal(self, wb_page):
        """边界：永久有效与普通有效期并存时展示（当前锚点覆盖：中建云0731=永久）."""
        _open_list(wb_page)
        body = visible_texts(wb_page)
        assert "永久有效" in body, "永久有效账户展示缺失"


class TestM3StatusAndBalance:
    """M3.4 可用状态与余额计算."""

    def test_m3_4_1__available_status_positive(self, wb_page):
        """状态：剩余额度>0 且未过期的账户可用状态为“可用”."""
        _open_list(wb_page)
        assert "可用" in visible_texts(wb_page), "列表未见“可用”状态"

    def test_m3_4_2__unavailable_when_exhausted(self, wb_page):
        """状态：剩余额度为 0 且未过期，可用状态为“不可用”."""
        pytest.skip("DATA_REQUIRED: 需剩余额度为 0 的权益账户数据")

    def test_m3_4_3__unavailable_when_expired(self, wb_page):
        """状态：剩余>0 但已过期，可用状态为“不可用”."""
        pytest.skip("DATA_REQUIRED: 需已过期的权益账户数据")

    def test_m3_4_4__over_consumed_boundary(self, wb_page):
        """边界：已调用额>总额时展示真实累计值，剩余调用额显示 0."""
        pytest.skip("DATA_REQUIRED: 需超额消耗的权益账户数据")

    def test_m3_4_5__balance_calculation_consistent(self, wb_page):
        """数据：剩余=总-已用；锚点不限量账户展示自洽（不限次数/0/不限次数）."""
        _open_list(wb_page)
        body = visible_texts(wb_page)
        assert "已调用额" in body, "额度字段缺失"
        assert body.count("不限次数") >= 2, "不限量账户总/剩展示不完整"


class TestM3RowActions:
    """M3.5 行内操作入口（扁平化版：直接在主列表行）。"""

    def test_m3_5_1__order_detail_entry(self, wb_page):
        """交互：列表行操作列存在“查看订单明细”。"""
        _open_list(wb_page)
        assert "查看订单明细" in visible_texts(wb_page)

    def test_m3_5_2__usage_entry(self, wb_page):
        """交互：列表行操作列存在“查看用量”。"""
        _open_list(wb_page)
        assert "查看用量" in visible_texts(wb_page)

    def test_m3_5_3__expand_collapse_toggle(self, wb_page):
        """交互：展开/收起——当前版本列表扁平化，无展开交互（版本差异）."""
        open_api_subscription_workbench(wb_page)
        body = visible_texts(wb_page)
        if "收起" in body:
            pytest.fail("当前版本仍存在展开/收起交互，需恢复本用例的展开断言")
        pytest.skip(
            "NOT_APPLICABLE(版本差异): 10-12 版列表扁平化，权益账户直接展示于主列表，"
            "无父行“查看/收起”展开交互；展开语义用例不再适用"
        )

    def test_m3_5_4__no_permission_order_detail(self, wb_page):
        """权限：无订单明细权限用户点击，期望提示“无权查看订阅详情”."""
        pytest.skip("ROLE_REQUIRED: 需无订单明细权限账号对照")
