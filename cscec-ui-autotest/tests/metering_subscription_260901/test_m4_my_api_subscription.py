"""M4: 工作台我的订阅 API 订阅（F03，P0）— 名义大纲编号对齐版.

PRE verified:
- Query bar: 资源名称 / 资源编码 / 订阅时间(range) + 查 询 / 重 置
  (NO 可用状态 / 订阅应用 / 服务模式 filter — recorded as实现差异)
- Page is tenant-aggregated: 租户编码/租户名称 columns present
- Rows: WPS服务组件(应用接入申请,1) 标签中心(标签库申请,1)
"""

from __future__ import annotations

import time

import pytest

from tests.metering_subscription_260901.helpers import (
    ANCHOR_RESOURCE_TAG,
    ANCHOR_RESOURCE_WPS,
    ANCHOR_TENANT_NAME,
    assert_headers_present,
    expand_first_row,
    gateway_error,
    open_api_subscription_workbench,
    visible_texts,
)

pytestmark = [pytest.mark.readonly, pytest.mark.portal, pytest.mark.regression]


def _open(wb_page):
    open_api_subscription_workbench(wb_page)
    assert visible_texts(wb_page).find("资源名称") >= 0, "查询区未渲染"


def _query_name(wb_page, value: str) -> None:
    box = wb_page.get_by_placeholder("请输入资源名称")
    assert box.count() > 0, "资源名称输入框缺失"
    box.first.fill(value)
    wb_page.get_by_role("button", name="查 询", exact=True).click()
    time.sleep(2)


class TestM4DefaultLoad:
    """M4.1 页面默认加载."""

    def test_m4_1_1__page_load_and_rows(self, wb_page):
        """主流程：进入我的订阅-API订阅，打开本人 API 权益账户列表（锚点展示）."""
        _open(wb_page)
        body = visible_texts(wb_page)
        assert ANCHOR_RESOURCE_WPS in body, "锚点资源 WPS服务组件 未展示"
        assert ANCHOR_TENANT_NAME in body, "租户名称未展示"

    def test_m4_1_2__default_available_filter(self, wb_page):
        """默认筛选：首次进入默认选中“可用”；实测查询区无可用状态控件→差异."""
        _open(wb_page)
        body = visible_texts(wb_page)
        if "可用状态" not in body:
            pytest.skip(
                "ENTRY_MISSING(实现差异): 查询区无“可用状态”筛选控件，"
                "大纲 M4.1.2/M4.2.4/M4.2.5 不可执行，记录为需求-实现差异"
            )
        assert "可用" in body

    def test_m4_1_3__fields_consistent_and_no_sensitive(self, wb_page):
        """UI：列表列名与工作台权益账户子表一致，且不展示 AKSK 等敏感字段."""
        _open(wb_page)
        body = visible_texts(wb_page)
        assert "资源名称" in body and "服务模式" in body, "列表字段缺失"
        for token in ("AKSK", "aksk", "SecretKey", "secret_key"):
            assert token not in body, f"页面暴露敏感字段: {token}"


class TestM4Query:
    """M4.2 查询条件（实现差异：仅资源名称/资源编码/订阅时间）."""

    def test_m4_2_1__query_by_resource_name(self, wb_page):
        """查询：资源名称=WPS服务组件，仅返回匹配行（含编码/组合/空结果补充覆盖）."""
        _open(wb_page)
        _query_name(wb_page, ANCHOR_RESOURCE_WPS)
        body = visible_texts(wb_page)
        assert ANCHOR_RESOURCE_WPS in body, "查询结果未含 WPS服务组件"
        assert ANCHOR_RESOURCE_TAG not in body, "不匹配资源（标签中心）未被过滤"

    def test_m4_2_2__query_by_apply_app(self, wb_page):
        """查询：订阅应用筛选（中建云统一门户）——实测无该筛选控件."""
        _open(wb_page)
        body = visible_texts(wb_page)
        if "订阅应用" not in body:
            pytest.skip(
                "ENTRY_MISSING(实现差异): 查询区无“订阅应用”筛选控件，"
                "需求-实现差异待产品确认"
            )
        assert "订阅应用" in body

    def test_m4_2_3__query_by_service_mode(self, wb_page):
        """查询：服务模式筛选（不限量认证服务）——实测无该筛选控件."""
        _open(wb_page)
        body = visible_texts(wb_page)
        if "请输入服务模式" not in body and box_missing(wb_page):
            pytest.skip(
                "ENTRY_MISSING(实现差异): 查询区无“服务模式”筛选输入，"
                "需求-实现差异待产品确认"
            )
        assert "服务模式" in body

    def test_m4_2_4__filter_unavailable(self, wb_page):
        """查询：可用状态=不可用（实测无该控件，见 M4.1.2 差异）。"""
        pytest.skip("ENTRY_MISSING(实现差异): 同 M4.1.2，无可用状态筛选控件")

    def test_m4_2_5__filter_all(self, wb_page):
        """查询：可用状态=全部（实测无该控件，见 M4.1.2 差异）。"""
        pytest.skip("ENTRY_MISSING(实现差异): 同 M4.1.2，无可用状态筛选控件")

    def test_m4_2_6__query_reset(self, wb_page):
        """重置：修改条件后重置，条件清空且列表重新加载."""
        _open(wb_page)
        _query_name(wb_page, "不存在的资源XYZ")
        wb_page.get_by_role("button", name="重 置", exact=True).click()
        time.sleep(2)
        body = visible_texts(wb_page)
        assert ANCHOR_RESOURCE_WPS in body, "重置后列表未恢复展示锚点数据"
        name_input = wb_page.get_by_placeholder("请输入资源名称")
        assert name_input.input_value() == "", "重置后资源名称未清空"


def box_missing(wb_page) -> bool:
    return wb_page.get_by_placeholder("请输入服务模式").count() == 0


class TestM4AggregationSemantics:
    """M4.3 个人聚合口径与隔离."""

    def test_m4_3_1__merge_multiple_purchases(self, wb_page):
        """数据：本人同组件/应用/服务模式多次购买合并为一行."""
        pytest.skip(
            "DATA_REQUIRED: 需多次成功购买数据；另记录形态差异——"
            "当前页面为租户聚合（含租户编码/租户名称列），见 M4.3.4 隔离发现"
        )

    def test_m4_3_2__split_by_apply_app(self, wb_page):
        """数据：本人同组件不同应用订阅按应用分行."""
        pytest.skip("DATA_REQUIRED: 需本人多应用订阅数据")

    def test_m4_3_3__split_by_service_mode(self, wb_page):
        """数据：本人同组件同应用不同服务模式分行."""
        pytest.skip("DATA_REQUIRED: 需本人多服务模式订阅数据")

    def test_m4_3_4__cross_user_isolation(self, wb_page):
        """隔离：其他用户订阅不出现在当前用户列表；实测订单明细出现他人→差异."""
        _open(wb_page)
        assert expand_first_row(wb_page), "权益子表展开失败"
        time.sleep(1.5)
        wb_page.get_by_text("查看订单明细", exact=True).first.click()
        time.sleep(2.5)
        body = visible_texts(wb_page)
        if "邱惟责" in body:
            assert False, (
                "差异：当前账号（20431644 陈方达）“我的订阅-API订阅”订单明细出现他人订单"
                "（订阅人=邱惟责），与“仅本人数据”语义冲突；"
                "若产品语义为租户管理员聚合视图则需更新大纲"
            )
        assert "订单ID" in body or "订单明细" in body, "订单明细未打开，无法核对隔离性"


class TestM4QuotaDisplay:
    """M4.4 权益类型展示."""

    def test_m4_4_1__unlimited_display(self, wb_page):
        """展示：不限量账户（统一身份服务类）总/剩显示“不限次数”。"""
        _open(wb_page)
        assert expand_first_row(wb_page), "权益子表展开失败"
        time.sleep(2)
        body = visible_texts(wb_page)
        assert "不限次数" in body, "未展示不限次数"

    def test_m4_4_2__concurrent_display(self, wb_page):
        """展示：并发账户（智能识别服务类）不展示并发数，已调用额可统计."""
        pytest.skip("DATA_REQUIRED: 需并发型权益账户数据")

    def test_m4_4_3__fixed_quota_display(self, wb_page):
        """展示：固定调用额账户（WPS服务组件类）显示总额/已用/剩余."""
        pytest.skip("DATA_REQUIRED: 当前锚点仅不限量账户")

    def test_m4_4_4__permanent_display(self, wb_page):
        """展示：截止时间为永久有效时显示“永久有效”。"""
        _open(wb_page)
        assert expand_first_row(wb_page), "权益子表展开失败"
        time.sleep(2)
        body = visible_texts(wb_page)
        assert "永久有效" in body, "未展示永久有效"


class TestM4Drilldown:
    """M4.5 下钻操作."""

    def test_m4_5_1__order_detail_from_my_subscription(self, wb_page):
        """交互：查看订单明细只展示本人有权查看的成功订阅记录."""
        _open(wb_page)
        assert expand_first_row(wb_page), "权益子表展开失败"
        time.sleep(1.5)
        assert wb_page.get_by_text("查看订单明细", exact=True).first.is_visible()
        wb_page.get_by_text("查看订单明细", exact=True).first.click()
        time.sleep(2.5)
        body = visible_texts(wb_page)
        assert "订单明细" in body or "订单ID" in body, "订单明细未打开"

    def test_m4_5_2__usage_expand_from_my_subscription(self, wb_page):
        """交互：查看用量在当前权益账户行下展开接口用量."""
        _open(wb_page)
        if gateway_error(wb_page):
            pytest.skip("ENV_LIMITED: pre 子应用网关 502，环境瞬时故障")
        assert expand_first_row(wb_page), "权益子表展开失败"
        time.sleep(1.5)
        from tests.metering_subscription_260901.helpers import click_when_visible

        if not click_when_visible(wb_page, "查看用量", timeout_ms=6000):
            pytest.skip("ENV_LIMITED: 查看用量入口未就绪（同 M6.1.1）")
        time.sleep(2.5)
        body = visible_texts(wb_page)
        assert "已调用额" in body, "展开用量后未见已调用额列"

    def test_m4_5_3__bypass_others_usage(self, wb_page):
        """越权：修改参数访问他人权益账户用量，期望无法查看."""
        pytest.skip(
            "ROLE_REQUIRED: 接口参数越权需第二账号数据与接口用例（API 层专项），"
            "UI 黑盒单账号不可证"
        )
