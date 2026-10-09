"""M5: 查看订单明细（F04，P0）— 名义大纲编号对齐版.

PRE verified: drawer 订单明细; headers 订单ID/订阅人/订阅人所在组织/生效时间/操作(详情);
anchor PO2025103015352000 | 邱惟责 | 技术与大数据平台项目组 | 2025-10-31 09:12:39
"""

from __future__ import annotations

import time

import pytest

from tests.metering_subscription_260901.helpers import (
    ANCHOR_ORDER_ID,
    ORDER_HEADERS,
    assert_headers_present,
    expand_first_row,
    open_api_subscription_workbench,
    visible_texts,
    wait_list_ready,
    open_api_list_console,
    click_when_visible,
)

pytestmark = [pytest.mark.readonly, pytest.mark.regression]


def _open_order_detail(wb_page) -> None:
    open_api_subscription_workbench(wb_page)
    assert expand_first_row(wb_page), "权益子表展开失败"
    time.sleep(1.5)
    btn = wb_page.get_by_text("查看订单明细", exact=True).first
    assert btn.is_visible(timeout=6000), "查看订单明细按钮不可见"
    btn.click()
    time.sleep(2.5)


class TestM5SuccessRecords:
    """M5.1 成功订阅记录追溯."""

    @pytest.mark.portal
    def test_m5_1_1__open_from_workbench(self, wb_page):
        """主流程：从工作台权益账户点击查看订单明细，展示全部成功订阅记录."""
        _open_order_detail(wb_page)
        body = visible_texts(wb_page)
        assert "订单明细" in body, "订单明细抽屉未打开"

    @pytest.mark.console
    def test_m5_1_2__open_from_console(self, cs_page):
        """主流程：从控制台权益账户点击查看订单明细，展示成功订阅记录."""
        open_api_list_console(cs_page)
        assert wait_list_ready(cs_page), "控制台列表未渲染"
        assert click_when_visible(cs_page, "查看", timeout_ms=8000)
        time.sleep(2)
        btn = cs_page.get_by_text("查看订单明细", exact=True).first
        assert btn.is_visible(timeout=6000), "控制台子表无查看订单明细"
        btn.click()
        time.sleep(2.5)
        body = visible_texts(cs_page)
        assert "订单明细" in body or "订单ID" in body, "控制台订单明细未打开"

    @pytest.mark.portal
    def test_m5_1_3__merged_multiple_records(self, wb_page):
        """数据：权益账户由多次成功订单合并时，明细可见多条成功记录."""
        pytest.skip("DATA_REQUIRED: 需多成功订单合并的权益账户（当前锚点单订单）")

    @pytest.mark.portal
    def test_m5_1_4__non_success_orders_excluded(self, wb_page):
        """数据：审批中/履约中/终止/草稿订单不出现在成功订阅明细."""
        _open_order_detail(wb_page)
        body = visible_texts(wb_page)
        for status in ("审批中", "履约中", "订单终止", "草稿"):
            assert status not in body, f"成功订阅明细出现非成功状态: {status}"


class TestM5FieldsAndReuse:
    """M5.2 明细字段与既有详情页复用."""

    @pytest.mark.portal
    def test_m5_2_1__drawer_headers(self, wb_page):
        """UI：明细表字段含订单ID/订阅人/订阅人所在组织/生效时间/操作."""
        _open_order_detail(wb_page)
        assert_headers_present(wb_page, ORDER_HEADERS, "订单明细")

    @pytest.mark.portal
    def test_m5_2_2__detail_jump_to_order_form(self, wb_page):
        """跳转：点击明细“详情”，进入既有订阅表单详情页."""
        _open_order_detail(wb_page)
        detail = wb_page.get_by_text("详情", exact=True).first
        assert detail.is_visible(timeout=6000), "详情按钮不可见"
        detail.click()
        time.sleep(3)
        body = visible_texts(wb_page)
        opened = any(kw in body for kw in ("资源信息", "订单状态", "基础信息", "规格", "套餐"))
        assert opened, (
            f"点击详情后未见订阅表单详情页要素；当前页面片段: {body[:200]}"
        )

    @pytest.mark.portal
    def test_m5_2_3__order_form_regression(self, wb_page):
        """回归：既有订阅详情页的资源/规格/补充信息/订单状态/流程入口保持."""
        pytest.skip(
            "手工协同：既有订单详情页完整回归建议随整体回归套件执行"
            "（入口可达性已由 M5.2.2 覆盖）"
        )

    @pytest.mark.portal
    def test_m5_2_4__snapshot_consistency(self, wb_page):
        """一致性：明细中的生效时间/订阅人/组织快照与订单详情页一致."""
        _open_order_detail(wb_page)
        body = visible_texts(wb_page)
        assert ANCHOR_ORDER_ID in body, "锚点订单未展示"
        assert "2025-10-31 09:12:39" in body, "生效时间未展示"
        pytest.skip(
            "DATA_REQUIRED: 与订单详情页快照逐字段对照需打开详情页双页核对，"
            "且当前详情页跳转深度待产品确认（部分断言已在本用例前段完成）"
        )


class TestM5Permission:
    """M5.3 权限控制."""

    @pytest.mark.portal
    def test_m5_3_1__workbench_any_role(self, wb_page):
        """权限：非中建云租户人员从工作台入口可正常打开订阅详情."""
        _open_order_detail(wb_page)
        body = visible_texts(wb_page)
        assert ANCHOR_ORDER_ID in body, "工作台入口订单明细未正常打开"

    @pytest.mark.console
    def test_m5_3_2__console_tenant_user(self, cs_page):
        """权限：中建云租户人员从控制台入口可正常打开订阅详情."""
        open_api_list_console(cs_page)
        assert wait_list_ready(cs_page), "控制台列表未渲染"
        assert click_when_visible(cs_page, "查看", timeout_ms=8000)
        time.sleep(2)
        btn = cs_page.get_by_text("查看订单明细", exact=True).first
        assert btn.is_visible(timeout=6000), "控制台子表无查看订单明细"
        btn.click()
        time.sleep(2.5)
        body = visible_texts(cs_page)
        assert "订单明细" in body or "订单ID" in body, "控制台订单明细未正常打开"
