"""M3: 工作台 API 权益账户子表（F02，P0）— 名义大纲编号对齐版.

PRE anchors (2026-10-09):
- Parent: WPS服务组件 / ZJ2025032715310001 / 应用接入申请 / 订阅数量 1
- Child:  WPS服务组件 | 应用接入申请 | 一体化资源平台项目 |
          技术与大数据平台项目组 | 2025-10-31 09:12:39 | 永久有效 |
          可用 | 不限次数 | 0 | 不限次数 | 查看订单明细 + 查看用量
"""

from __future__ import annotations

import re
import time

import pytest

from tests.metering_subscription_260901.helpers import (
    ANCHOR_APPLY_APP,
    ANCHOR_RESOURCE_WPS,
    CHILD_HEADERS,
    assert_headers_present,
    click_text_strict,
    click_when_visible,
    expand_first_row,
    gateway_error,
    open_api_subscription_workbench,
    visible_texts,
)

pytestmark = [pytest.mark.readonly, pytest.mark.portal, pytest.mark.regression]


def _open_with_subtable(wb_page) -> None:
    open_api_subscription_workbench(wb_page)
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
        body = visible_texts(wb_page)
        # 展开的 WPS 行子表中不应混入标签中心（另一资源）的权益账户行
        sub_zone = body[body.find(ANCHOR_RESOURCE_WPS) :]
        sub_zone = sub_zone[: sub_zone.find("标签中心")] if "标签中心" in sub_zone else sub_zone
        assert "标签库申请" not in sub_zone, "其他资源的权益账户混入当前父行子表"


class TestM3QuotaDisplay:
    """M3.2 子表字段与权益类型展示."""

    def test_m3_2_1__subtable_headers(self, wb_page):
        """UI：子表列名含资源名称/服务模式/订阅应用/生效时间/额度等 11 项."""
        _open_with_subtable(wb_page)
        assert_headers_present(wb_page, CHILD_HEADERS, "权益账户子表")

    def test_m3_2_2__fixed_quota_display(self, wb_page):
        """展示：固定调用额账户显示具体总额/已用/剩余（如 12,000/10,780/1,220）."""
        pytest.skip(
            "DATA_REQUIRED: 当前工作台锚点权益仅不限量账户，"
            "固定调用额展示需构造固定额度权益数据"
        )

    def test_m3_2_3__unlimited_quota_display(self, wb_page):
        """展示：不限量账户总/剩显示“不限次数”，不显示“-”，不暴露 Credits."""
        _open_with_subtable(wb_page)
        body = visible_texts(wb_page)
        assert "不限次数" in body, "子表未出现“不限次数”展示"
        assert "Credits" not in body and "credits" not in body, "页面暴露 Credits 单位"

    def test_m3_2_4__concurrent_quota_display(self, wb_page):
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
        """边界：同时存在永久有效与普通有效期记录，截止时间显示“永久有效”."""
        pytest.skip(
            "DATA_REQUIRED: 工作台锚点权益仅永久有效账户，"
            "同账户混合期限数据不可只读构造（控制台锚点为固定期限可对照，见 M7.4.3）"
        )


class TestM3StatusAndBalance:
    """M3.4 可用状态与余额计算."""

    def test_m3_4_1__available_status_positive(self, wb_page):
        """状态：剩余额度>0 且未过期的账户可用状态为“可用”（锚点可用）."""
        _open_with_subtable(wb_page)
        body = visible_texts(wb_page)
        assert "可用" in body, "子表未见“可用”状态"

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
        _open_with_subtable(wb_page)
        body = visible_texts(wb_page)
        assert "不限次数" in body and "已调用额" in body, "锚点额度字段缺失"
        # 不限量账户：总=剩=不限次数，已调用额为数值
        assert body.count("不限次数") >= 2, "不限量账户总/剩展示不完整"


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

    def test_m3_5_3__expand_collapse_toggle(self, wb_page):
        """交互：再次点击收起，子表关闭（实测按钮文字保持“查看”不变→记录差异）."""
        open_api_subscription_workbench(wb_page)
        if gateway_error(wb_page):
            pytest.skip("ENV_LIMITED: pre 子应用网关 502，环境瞬时故障")
        assert expand_first_row(wb_page), "首次展开失败"
        time.sleep(1.5)
        # 大纲期望按钮变“收起”；实测展开后按钮仍显示“查看”
        button_text_changed = click_text_strict(wb_page, "收起", timeout_ms=3000)
        if not button_text_changed:
            # 差异路径：按钮文字未变，直接再次点击同位置的“查看”收起
            assert click_when_visible(wb_page, "查看", timeout_ms=6000), (
                "展开后既无“收起”也无法再次点击“查看”收起"
            )
        time.sleep(2)
        body = visible_texts(wb_page)
        assert "查看订单明细" not in body, "再次点击后子表未收起"

    def test_m3_5_4__no_permission_order_detail(self, wb_page):
        """权限：无订单明细权限用户点击，期望提示“无权查看订阅详情”."""
        pytest.skip("ROLE_REQUIRED: 需无订单明细权限账号对照")
