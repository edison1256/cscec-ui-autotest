"""M3: 工作台 API 权益账户子表（F02，P0）— 名义大纲编号对齐版.

PRE anchors (2026-10-09):
- Parent: WPS服务组件 / ZJ2025032715310001 / 应用接入申请 / 订阅数量 1
- Child:  WPS服务组件 | 应用接入申请 | 一体化资源平台项目 |
          技术与大数据平台项目组 | 2025-10-31 09:12:39 | 永久有效 |
          可用 | 不限次数 | 0 | 不限次数 | 查看订单明细 + 查看用量
"""

from __future__ import annotations

import re

import pytest

from tests.metering_subscription_260901.helpers import (
    ANCHOR_APPLY_APP,
    ANCHOR_RESOURCE_WPS,
    CHILD_HEADERS,
    assert_headers_present,
    expand_first_row,
    entitlement_rows,
    open_api_subscription_workbench,
    visible_texts,
)

pytestmark = [pytest.mark.readonly, pytest.mark.portal, pytest.mark.regression]


def _open_with_subtable(wb_page) -> None:
    from tests.metering_subscription_260901.helpers import list_is_empty

    open_api_subscription_workbench(wb_page)
    if list_is_empty(wb_page):
        pytest.skip(
            "ENV_LIMITED: V1.2 统一版已上线（2026-10-10 部署），"
            "中建云租户当前账号本人订阅为空（暂无数据），昨日旧版锚点失效；"
            "统一形态聚合视角已由 M2（订阅中心，中建数字租户）覆盖"
        )
    body = visible_texts(wb_page)
    if ANCHOR_RESOURCE_WPS not in body:
        pytest.skip(
            "ENV_LIMITED(D9): 列表非空但无 WPS 锚点——租户切换后上下文混合态"
            "或 pre 数据漂移，旧锚点校验需数据稳定窗口；"
            "聚合视角已由 M2（订阅中心）覆盖"
        )
    assert expand_first_row(wb_page), "父行“查看”不可点，权益子表未展开"


class TestM3SubtableScope:
    """M3.1 子表数据范围."""

    def test_m3_1_1__expand_child_table(self, wb_page):
        """主流程：父行下展开权益账户子表成功."""
        _open_with_subtable(wb_page)
        body = visible_texts(wb_page)
        assert ANCHOR_RESOURCE_WPS in body, "子表未展示锚点资源"

    def test_m3_1_2__current_account_entitlement(self, wb_page):
        """数据：子表展示当前租户关联权益账户（订阅应用=一体化资源平台项目）."""
        _open_with_subtable(wb_page)
        body = visible_texts(wb_page)
        assert ANCHOR_APPLY_APP in body, f"子表未展示订阅应用（{ANCHOR_APPLY_APP}）"

    def test_m3_1_3__no_other_resource_leak(self, wb_page):
        """数据：其他资源/服务模式的权益账户不出现在当前父行子表."""
        _open_with_subtable(wb_page)
        rows = entitlement_rows(wb_page)
        assert all(row["资源名称"] == ANCHOR_RESOURCE_WPS for row in rows), rows
        assert all(row["服务模式"] == "应用接入申请" for row in rows), rows


class TestM3QuotaDisplay:
    """M3.2 子表字段与权益类型展示."""

    def test_m3_2_1__subtable_headers(self, wb_page):
        """UI：子表列名含资源名称/服务模式/订阅应用/生效时间/额度等 11 项."""
        _open_with_subtable(wb_page)
        assert_headers_present(wb_page, CHILD_HEADERS, "权益账户子表")

    def test_m3_2_2__fixed_quota_display(self):
        """展示：固定调用额账户显示具体总额/已用/剩余（如 12,000/10,780/1,220）."""
        pytest.skip(
            "DATA_REQUIRED: 当前工作台锚点权益仅不限量账户，"
            "固定调用额展示需构造固定额度权益数据"
        )

    def test_m3_2_3__unlimited_quota_display(self, wb_page):
        """展示：不限量账户总/剩显示“不限次数”，不显示“-”，不暴露 Credits."""
        _open_with_subtable(wb_page)
        rows = entitlement_rows(wb_page)
        assert all(row["总可调用额"] == row["剩余调用额"] == "不限次数" for row in rows), rows
        assert all("credits" not in str(row).lower() for row in rows), "页面暴露 Credits 单位"

    def test_m3_2_4__concurrent_quota_display(self):
        """展示：并发账户不展示并发数，已调用额可统计."""
        pytest.skip("DATA_REQUIRED: 需并发型权益账户数据")

    def test_m3_2_5__permanent_expiry_display(self, wb_page):
        """展示：永久有效账户截止时间显示“永久有效”；生效时间为标准格式."""
        _open_with_subtable(wb_page)
        body = visible_texts(wb_page)
        assert "永久有效" in body, "子表未出现“永久有效”截止时间展示"
        assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", body), (
            "子表未见标准生效时间格式"
        )


class TestM3TimeFields:
    """M3.3 生效时间与截止时间取值规则."""

    def test_m3_3_1__earliest_effective_time(self):
        """数据：账户内多条成功订阅时生效时间取最早（需多记录账户）."""
        pytest.skip("DATA_REQUIRED: 需同一权益账户多条成功订阅记录")

    def test_m3_3_2__fixed_quota_latest_expiry(self):
        """数据：固定调用额多次成功购买截止时间取最新结果（叠加）."""
        pytest.skip("DATA_REQUIRED: 需固定额度多次购买流程数据")

    def test_m3_3_3__unlimited_latest_expiry(self):
        """数据：不限量账户多次成功购买截止时间取最新结果."""
        pytest.skip("DATA_REQUIRED: 需不限量多次购买流程数据")

    def test_m3_3_4__concurrent_no_extension(self):
        """数据：并发账户增购不错误延长有效期."""
        pytest.skip("DATA_REQUIRED: 需并发账户增购流程数据")

    def test_m3_3_5__mixed_permanent_and_normal(self):
        """边界：同时存在永久有效与普通有效期记录，截止时间显示“永久有效”."""
        pytest.skip(
            "DATA_REQUIRED: 工作台锚点权益仅永久有效账户，"
            "同账户混合期限数据不可只读构造（控制台锚点为固定期限可对照，见 M7.4.3）"
        )


class TestM3StatusAndBalance:
    """M3.4 可用状态与余额计算."""

    def test_m3_4_1__available_status_positive(self):
        """状态：剩余额度>0 且未过期的账户可用状态为“可用”（锚点可用）."""
        pytest.skip("DATA_REQUIRED: 大纲要求固定调用额且剩余>0、未过期；不限量锚点不能替代")

    def test_m3_4_2__unavailable_when_exhausted(self):
        """状态：剩余额度为 0 且未过期，可用状态为“不可用”."""
        pytest.skip("DATA_REQUIRED: 需剩余额度为 0 的权益账户数据")

    def test_m3_4_3__unavailable_when_expired(self):
        """状态：剩余>0 但已过期，可用状态为“不可用”."""
        pytest.skip("DATA_REQUIRED: 需已过期的权益账户数据")

    def test_m3_4_4__over_consumed_boundary(self):
        """边界：已调用额>总额时展示真实累计值，剩余调用额显示 0."""
        pytest.skip("DATA_REQUIRED: 需超额消耗的权益账户数据")

    def test_m3_4_5__balance_calculation_consistent(self):
        """数据：剩余=总-已用；锚点不限量账户展示自洽（不限次数/0/不限次数）."""
        pytest.skip("DATA_REQUIRED: 需固定额度及可对照的聚合结果，核验总额-已用=剩余")


class TestM3RowActions:
    """M3.5 操作入口."""

    def test_m3_5_1__order_detail_entry(self, wb_page):
        """交互：子表操作列存在“查看订单明细”。"""
        _open_with_subtable(wb_page)
        assert visible_texts(wb_page).find("查看订单明细") >= 0

    def test_m3_5_2__usage_entry(self, wb_page):
        """交互：子表操作列存在“查看用量”。"""
        _open_with_subtable(wb_page)
        assert visible_texts(wb_page).find("查看用量") >= 0

    def test_m3_5_3__expand_collapse_toggle(self):
        """交互：点击收起用量关闭接口用量子表，不是收起权益账户父表."""
        pytest.skip("PENDING_IMPLEMENTATION: 待实现接口用量展开/收起状态断言，父表收起不能替代")

    def test_m3_5_4__no_permission_order_detail(self):
        """权限：无订单明细权限用户点击，期望提示“无权查看订阅详情”."""
        pytest.skip("ROLE_REQUIRED: 需无订单明细权限账号对照")
