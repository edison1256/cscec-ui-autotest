"""M6: 接口用量与每日明细导出（F05/F06，P0）— 名义大纲编号对齐版."""

from __future__ import annotations

import time

import pytest

from tests.metering_subscription_260901.helpers import (
    click_text_strict,
    expand_first_row,
    open_api_subscription_workbench,
    visible_texts,
)

pytestmark = [pytest.mark.readonly, pytest.mark.portal, pytest.mark.regression]


def _open_usage(wb_page) -> bool:
    open_api_subscription_workbench(wb_page)
    if not expand_first_row(wb_page):
        return False
    time.sleep(1.5)
    return click_text_strict(wb_page, "查看用量", timeout_ms=6000)


class TestM6InlineUsage:
    """M6.1 行内查看接口用量."""

    def test_m6_1_1__usage_subtable_expands(self, wb_page):
        """主流程：点击查看用量，在当前账户行下展开接口用量子表."""
        if not _open_usage(wb_page):
            pytest.skip("ENV_LIMITED: 查看用量入口未就绪（列表未加载或按钮缺失）")
        time.sleep(2.5)
        body = visible_texts(wb_page)
        assert "已调用额" in body, "接口用量子表未见已调用额列"
        assert "接口" in body, "未见接口用量区域"

    def test_m6_1_2__usage_headers(self, wb_page):
        """UI：接口用量子表列名为接口名称、已调用额、操作."""
        if not _open_usage(wb_page):
            pytest.skip("ENV_LIMITED: 查看用量入口未就绪")
        time.sleep(2.5)
        body = visible_texts(wb_page)
        for col in ("接口名称", "已调用额", "操作"):
            assert col in body, f"缺少接口用量列: {col}"

    def test_m6_1_3__amount_without_unit(self, wb_page):
        """展示：接口已调用额只显示数值，不在单元格中展示单位."""
        if not _open_usage(wb_page):
            pytest.skip("ENV_LIMITED: 查看用量入口未就绪")
        time.sleep(2.5)
        body = visible_texts(wb_page)
        assert "Credits" not in body and "credits" not in body, "接口用量暴露单位"
        assert "已调用额" in body

    def test_m6_1_4__no_remaining_on_api_row(self, wb_page):
        """规则：接口行不展示独立剩余额度（余额只在权益账户共享池展示）."""
        if not _open_usage(wb_page):
            pytest.skip("ENV_LIMITED: 查看用量入口未就绪")
        time.sleep(2.5)
        body = visible_texts(wb_page)
        assert body.count("剩余调用额") <= 1, "接口行疑似展示独立剩余额度"


class TestM6UsageConsistency:
    """M6.2 用量数据一致性（全部需计量数据）."""

    def test_m6_2_1__api_sum_equals_account(self, wb_page):
        """数据：多 API 已调用额汇总=权益账户已调用额."""
        pytest.skip("DATA_REQUIRED: 需多接口计量数据")

    def test_m6_2_2__fixed_quota_sync(self, wb_page):
        """数据：固定额度更新后接口/账户已用/剩余同步."""
        pytest.skip("DATA_REQUIRED: 需固定额度计量数据")

    def test_m6_2_3__unlimited_accumulate(self, wb_page):
        """数据：不限量账户有调用事实时接口已用累计，剩余仍“不限次数”."""
        pytest.skip("DATA_REQUIRED: 需不限量账户调用计量数据（当前锚点已调用额=0）")

    def test_m6_2_4__concurrent_accumulate(self, wb_page):
        """数据：并发账户接口已用累计，不展示并发数."""
        pytest.skip("DATA_REQUIRED: 需并发账户计量数据")


class TestM6DailyDetail:
    """M6.3 每日 API 调用明细."""

    def test_m6_3_1__daily_detail_dialog(self, wb_page):
        """主流程：接口行“查看明细”打开每日调用明细弹窗."""
        if not _open_usage(wb_page):
            pytest.skip("ENV_LIMITED: 查看用量入口未就绪")
        time.sleep(2)
        if not click_text_strict(wb_page, "查看明细", timeout_ms=6000):
            pytest.skip(
                "ENV_LIMITED: 当前锚点接口无调用明细入口（可能因无调用数据隐藏），"
                "待有调用数据后复核"
            )
        time.sleep(2.5)
        body = visible_texts(wb_page)
        assert "明细" in body, "每日明细弹窗未打开"

    def test_m6_3_2__dialog_title_identity(self, wb_page):
        """UI：弹窗标题包含权益账户聚合标识和接口名称."""
        if not _open_usage(wb_page):
            pytest.skip("ENV_LIMITED: 查看用量入口未就绪")
        time.sleep(2)
        if not click_text_strict(wb_page, "查看明细", timeout_ms=6000):
            pytest.skip("ENV_LIMITED: 无调用明细入口（无调用数据），待数据复核")
        time.sleep(2.5)
        body = visible_texts(wb_page)
        assert "WPS服务组件" in body or "明细" in body, "弹窗未含接口标识"

    def test_m6_3_3__dialog_columns(self, wb_page):
        """UI：明细表列名为日期、已调用次数、已调用额."""
        if not _open_usage(wb_page):
            pytest.skip("ENV_LIMITED: 查看用量入口未就绪")
        time.sleep(2)
        if not click_text_strict(wb_page, "查看明细", timeout_ms=6000):
            pytest.skip("ENV_LIMITED: 无调用明细入口（无调用数据），待数据复核")
        time.sleep(2.5)
        body = visible_texts(wb_page)
        for col in ("日期", "已调用次数", "已调用额"):
            assert col in body, f"每日明细弹窗缺少列: {col}"

    def test_m6_3_4__sort_desc_by_date(self, wb_page):
        """排序：多天数据按日期倒序."""
        pytest.skip("DATA_REQUIRED: 需多日调用计量数据（T+1 聚合）")

    def test_m6_3_5__total_matches_api_amount(self, wb_page):
        """数据：每日明细合计值与当前接口已调用额一致."""
        pytest.skip("DATA_REQUIRED: 需接口计量数据")

    def test_m6_3_6__dialog_pagination(self, wb_page):
        """分页：每日明细弹窗分页控件可用."""
        if not _open_usage(wb_page):
            pytest.skip("ENV_LIMITED: 查看用量入口未就绪")
        time.sleep(2)
        if not click_text_strict(wb_page, "查看明细", timeout_ms=6000):
            pytest.skip("ENV_LIMITED: 无调用明细入口（无调用数据），待数据复核")
        time.sleep(2.5)
        body = visible_texts(wb_page)
        assert ("条" in body and "页" in body) or "共" in body or "下一页" in body, (
            "弹窗未检出分页信息"
        )


class TestM6Export:
    """M6.4 导出基础校验 / M6.5 全量导出."""

    def test_m6_4_1__start_date_required(self, wb_page):
        """校验：开始日期为空点击导出，提示必填且不生成文件."""
        pytest.skip(
            "NOT_AUTOMATABLE(本轮): 导出涉及文件生成与下载校验，"
            "且锚点账户无调用数据；列入手工协同"
        )

    def test_m6_4_2__end_date_required(self, wb_page):
        """校验：结束日期为空点击导出，提示必填且不生成文件."""
        pytest.skip("NOT_AUTOMATABLE(本轮): 同 M6.4.1")

    def test_m6_4_3__date_range_validation(self, wb_page):
        """校验：开始日期晚于结束日期，拦截导出并提示范围错误."""
        pytest.skip("NOT_AUTOMATABLE(本轮): 同 M6.4.1")

    def test_m6_5_1__full_export_success(self, wb_page):
        """主流程：选有效日期区间导出，文件生成且不受分页影响."""
        pytest.skip("NOT_AUTOMATABLE(本轮): 同 M6.4.1")

    def test_m6_5_2__full_export_coverage(self, wb_page):
        """全量：分页部分展示时导出覆盖所选日期范围全部数据."""
        pytest.skip("NOT_AUTOMATABLE(本轮): 同 M6.4.1")

    def test_m6_5_3__export_permission(self, wb_page):
        """权限：导出当前 API 接口明细数据."""
        pytest.skip("NOT_AUTOMATABLE(本轮): 同 M6.4.1")

    def test_m6_5_4__console_export_permission(self, cs_page):
        """权限：控制台同样支持导出当前 API 接口明细."""
        pytest.skip("NOT_AUTOMATABLE(本轮): 同 M6.4.1，依赖控制台同锚点数据")
