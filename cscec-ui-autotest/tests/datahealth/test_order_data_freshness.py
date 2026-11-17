"""数据健康度用例集：列表数据「时效性」。

与 tests/console 的分工：
- tests/console 验「页面可达 + 有数据」
- 本目录验「数据是活的」—— 首条记录时间距现在多久

单独成目录的两个原因：
1. `tools/validate_prod_console_contracts.py` 硬编码 tests/console 全量节点 == 113，
   往那里加用例会破坏契约门禁；
2. 这是跨模块的横向维度（订单/订阅/工单/审批/消息都要查），
   按业务模块切开放会重复写同一套断言。

起因（2026-11-17 生产走查）：订单中心近期订单整体不显示，但历史数据仍在、
total 仍为 2375，页面文案断言完全通过。
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from config.settings import settings
from core.data_freshness import assert_fresh, check_freshness
from pages.console.order_mgmt_page import OrderMgmtPage

pytestmark = [
    pytest.mark.datahealth,
    pytest.mark.console,
    pytest.mark.readonly,
]

# 订单业务应每日都有新单；阈值取 3 天以覆盖周末。长假期会误报，
# 失败信息里已提示需人工确认。
ORDER_MAX_AGE_DAYS = 3.0


@pytest.fixture(scope="function")
def order_page(logged_in_page) -> OrderMgmtPage:
    return OrderMgmtPage(logged_in_page)


class TestOrderDataFreshness:
    """订单列表数据时效性。"""

    def test_dh_order_001_list_has_records(
        self, order_page: OrderMgmtPage
    ) -> None:
        """DH-ORDER-001：订单列表接口必须返回记录且 total > 0。"""
        rows, total = order_page.capture_order_list()
        assert rows, (
            f"订单列表接口返回空列表（total={total}）。"
            "若这是预期（全新环境），请在此环境禁用本用例"
        )
        if total is not None:
            assert total > 0, f"订单列表 total 为 {total}"

    def test_dh_order_002_latest_record_is_recent(
        self, order_page: OrderMgmtPage
    ) -> None:
        """DH-ORDER-002：订单列表最新一条记录距今不超过 3 天。

        这是 2026-11-17 走查 bug 的守门用例：
        「历史订单还在、近期订单不显示」时，记录非空、total 正常，
        只有时间新鲜度能发现。
        """
        rows, total = order_page.capture_order_list()
        report = assert_fresh(
            rows,
            label="订单列表",
            threshold_days=ORDER_MAX_AGE_DAYS,
            total=total,
        )
        # 附带记录一条通过信息，便于对比不同日期的数据水位
        assert report.latest is not None
        print(f"\n[数据水位] {report.describe()}")


class TestOrderFreshnessSelfCheck:
    """对判据本身的自检：确保断言不会退化成永远通过。"""

    def test_dh_order_003_stale_data_is_detected(self) -> None:
        """DH-ORDER-003：构造 10 天前的记录，判据必须判为不新鲜。

        防止有人为了「让门禁变绿」而放宽阈值 —— 这个用例会先失败。
        """
        now = datetime.now()
        stale_row = {
            "insertDt": (now - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
        }
        report = check_freshness(
            [stale_row],
            label="自检样本",
            threshold_days=ORDER_MAX_AGE_DAYS,
            now=now,
        )
        assert report.stale, (
            f"自检失败：10 天前的数据未被判为不新鲜（{report.describe()}），"
            "说明新鲜度判据已失效"
        )

    def test_dh_order_004_missing_time_field_fails(self) -> None:
        """DH-ORDER-004：记录里没有可解析时间字段时必须失败，不能静默通过。"""
        now = datetime.now()
        report = check_freshness(
            [{"someRenamedField": "x"}],
            label="自检样本",
            threshold_days=ORDER_MAX_AGE_DAYS,
            now=now,
        )
        assert report.latest is None, "时间字段全缺失时 latest 应为 None"
        assert not report.stale, "latest 为 None 时不应判 stale（由 assert_fresh 负责报错）"
