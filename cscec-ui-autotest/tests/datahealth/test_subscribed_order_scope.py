"""数据归属判据的自检用例（不访问页面）。

起因（2026-11-17 用户走查）：
  个人工作台下「订单中心 → 被订阅的订单」返回了**全量**数据，
  而不是当前账户的订单。生产实测：

      POST /irp-api/irp-portal-console/workbench/rsc/app/apply/history/list
      total=828，tenantNo 去重 26 个不同租户
      当前账号 tenantNo=ZH_01_0000

判据：`suitKey=portal` 是「个人工作台」套件，进了这个套件就应按"我的"收口，
与登录账号是不是平台管理员无关 —— 个人视角不该出现别的租户的数据。
"""

from __future__ import annotations

import pytest

from core.data_scope import assert_scope, check_scope

pytestmark = [
    pytest.mark.datahealth,
    pytest.mark.console,
    pytest.mark.readonly,
]


class TestScopeJudgeSelfCheck:
    """判据自检：确保归属断言不会退化成永远通过。"""

    def test_dh_scope_003_cross_tenant_is_detected(self) -> None:
        """DH-SCOPE-003：构造跨租户数据，判据必须判为越权。"""
        rows = (
            [{"tenantNo": "ZH_01_0000"}] * 3
            + [{"tenantNo": "ZH_01_0000_0044"}] * 5
        )
        report = check_scope(
            rows, label="自检样本", expected="ZH_01_0000", total=8
        )
        assert report.leaked, (
            f"自检失败：跨租户数据未被判为越权（{report.describe()}）"
        )
        assert "ZH_01_0000_0044" in report.out_of_scope, "越权租户未被列出"

    def test_dh_scope_004_single_tenant_passes(self) -> None:
        """DH-SCOPE-004：全部同一租户时必须判为合规。"""
        rows = [{"tenantNo": "ZH_01_0000"}] * 10
        report = check_scope(
            rows, label="自检样本", expected="ZH_01_0000", total=10
        )
        assert not report.leaked, f"自检失败：单租户数据被误判越权（{report.describe()}）"

    def test_dh_scope_005_missing_field_fails_loudly(self) -> None:
        """DH-SCOPE-005：归属字段缺失时必须抛错，不能静默通过。"""
        with pytest.raises(AssertionError, match="找不到任何归属字段"):
            assert_scope(
                [{"someOtherField": "x"}],
                label="自检样本",
                expected="ZH_01_0000",
            )
