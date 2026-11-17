"""个人工作台「被订阅的订单」数据归属（越权）用例。

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

from core.data_scope import (
    assert_scope,
    check_scope,
    looks_like_platform_admin,
    tenant_signature,
)
from pages.console.order_mgmt_page import OrderMgmtPage

pytestmark = [
    pytest.mark.datahealth,
    pytest.mark.console,
    pytest.mark.readonly,
]


@pytest.fixture(scope="function")
def order_page(logged_in_page) -> OrderMgmtPage:
    return OrderMgmtPage(logged_in_page)


def _login_info(page) -> dict:
    """读当前登录态（tenantNo / orgName 等）。"""
    try:
        info = page.evaluate(
            "() => { const s = localStorage.getItem('__login_info__');"
            " return s ? JSON.parse(s) : null; }"
        )
    except Exception:
        return {}
    return info if isinstance(info, dict) else {}


class TestSubscribedOrderScope:
    """被订阅的订单：数据范围不得越出当前账户。"""

    def test_dh_scope_001_subscribed_orders_within_account(
        self, order_page: OrderMgmtPage
    ) -> None:
        """DH-SCOPE-001：被订阅订单的归属租户必须收口到当前账号。

        用 `pytest.xfail` 标注为已知缺陷：修复后会自动变成 xpass，
        届时需移除标记并转为硬断言。
        """
        rows, total, _payload = order_page.capture_subscribed_orders()
        assert rows, f"被订阅的订单接口返回空列表（total={total}）"

        info = _login_info(order_page.page)
        expected = tenant_signature(info)
        assert expected, (
            "无法从登录态解析当前账号的 tenantNo，不能判断数据归属；"
            f"login_info keys={list(info)[:8]}"
        )

        report = check_scope(
            rows,
            label="被订阅的订单",
            expected=expected,
            total=total,
        )
        print(f"\n[归属] {report.describe()}")

        if report.leaked:
            platform = looks_like_platform_admin(info)
            pytest.xfail(
                f"已知缺陷：个人工作台返回跨租户数据。{report.describe()}；"
                f"当前身份 orgName={info.get('orgName')}，"
                f"平台管理侧={platform}"
            )

        # 未越权时给出显式通过信息
        assert not report.leaked, report.describe()

    def test_dh_scope_002_order_list_within_account(
        self, order_page: OrderMgmtPage
    ) -> None:
        """DH-SCOPE-002：控制台「我的订单」归属同样不得越界。

        作为对照组：个人工作台越权时，我的订单是否也越权。
        """
        rows, total = order_page.capture_order_list()
        assert rows, f"订单列表接口返回空列表（total={total}）"

        info = _login_info(order_page.page)
        expected = tenant_signature(info)
        if not expected:
            pytest.skip("NOT_APPLICABLE[DH-SCOPE-002] 登录态缺少 tenantNo")

        report = check_scope(
            rows,
            label="我的订单",
            expected=expected,
            total=total,
        )
        print(f"\n[归属] {report.describe()}")

        if report.leaked:
            pytest.xfail(
                f"已知范围问题：我的订单返回跨租户数据。{report.describe()}"
            )
        assert not report.leaked, report.describe()


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
