"""个人工作台各列表的数据归属（越权）用例。

起因（2026-11-17 用户走查）：个人工作台下「被订阅的订单」返回全量数据。
按此线索扫描个人工作台「常用模块」，发现**四个列表全部越权**：

| 列表 | 接口 | total | 越权规模 |
| --- | --- | --- | --- |
| 被订阅的订单 | workbench/rsc/app/apply/history/list | 828 | 26 租户 / 57 用户 |
| 云产品订阅 | cloud/applyList | 554 | 8 租户 / 10 用户 |
| 数据资产订阅 | workbench/rsc/data/apply/history/list | 16 | 2 租户 / 6 用户 |
| 订单管理（我的订单） | order/page | 2376 | creator 12 人 |

当前账号 userNo=20431644 / tenantNo=ZH_01_0000。

判据：`suitKey=portal` 是「个人工作台」套件，进了这个套件所有列表都应按
「我的」收口，与登录账号是否平台管理员无关。

已知缺陷，全部用 `pytest.xfail` 标注：修复后自动 xpass，届时移除标记转硬断言。
"""

from __future__ import annotations

import pytest

from core.data_scope import check_scope, tenant_signature
from pages.console.personal_workbench_page import PersonalWorkbenchPage

pytestmark = [
    pytest.mark.datahealth,
    pytest.mark.console,
    pytest.mark.readonly,
]


@pytest.fixture(scope="function")
def workbench(logged_in_page) -> PersonalWorkbenchPage:
    return PersonalWorkbenchPage(logged_in_page)


def _tenant_scope(page: PersonalWorkbenchPage) -> tuple[str, ...]:
    info = page.login_info()
    return tenant_signature(info)


def _assert_tenant_scoped(
    page: PersonalWorkbenchPage,
    *,
    label: str,
    entry_label: str,
    api_hint: str,
) -> None:
    """按租户口径断言某个列表的归属。"""
    rows, total = page.capture_list(entry_label, api_hint)
    assert rows, f"{label}: 接口返回空列表（total={total}）"

    expected = _tenant_scope(page)
    assert expected, f"{label}: 登录态缺少 tenantNo，无法判断归属"

    report = check_scope(rows, label=label, expected=expected, total=total)
    print(f"\n[归属] {report.describe()}")

    if report.leaked:
        pytest.xfail(f"已知缺陷：{label} 返回跨租户数据。{report.describe()}")
    assert not report.leaked, report.describe()


@pytest.mark.skip(
    reason=(
        "黑盒路径待打通：进控制台后落地页不是工作台，找不到「常用模块」卡片。"
        "此前用 suitKey=portal 直链得出的越权结论已作废（绕过视图选择），"
        "需先确认『门户→管理后台→控制台』或『直连 irp 后点工作台』的稳定路径，"
        "再用 orgNo 作为归属基准重跑。"
    )
)
class TestWorkbenchListScope:
    """个人工作台各列表的归属范围（路径待通，结论待重验）。"""

    def test_dh_scope_101_subscribed_orders(
        self, workbench: PersonalWorkbenchPage
    ) -> None:
        """DH-SCOPE-101：被订阅的订单只应包含当前账号的数据。"""
        _assert_tenant_scoped(
            workbench,
            label="被订阅的订单",
            entry_label="被订阅的订单",
            api_hint="workbench/rsc/app/apply/history/list",
        )

    def test_dh_scope_102_cloud_subscription(
        self, workbench: PersonalWorkbenchPage
    ) -> None:
        """DH-SCOPE-102：云产品订阅只应包含当前账号的数据。"""
        _assert_tenant_scoped(
            workbench,
            label="云产品订阅",
            entry_label="云产品订阅",
            api_hint="cloud/applyList",
        )

    def test_dh_scope_103_data_asset_subscription(
        self, workbench: PersonalWorkbenchPage
    ) -> None:
        """DH-SCOPE-103：数据资产订阅只应包含当前账号的数据。"""
        _assert_tenant_scoped(
            workbench,
            label="数据资产订阅",
            entry_label="数据资产订阅",
            api_hint="workbench/rsc/data/apply/history/list",
        )

    def test_dh_scope_104_my_orders_by_creator(
        self, workbench: PersonalWorkbenchPage
    ) -> None:
        """DH-SCOPE-104：「我的订单」按创建人判定，只应包含本人订单。

        该列表没有 tenantNo，只有 creator（用户账号），因此字段与期望都换成
        创建人口径。
        """
        rows, total = workbench.capture_list("订单管理", "order/page")
        assert rows, f"我的订单: 接口返回空列表（total={total}）"

        info = workbench.login_info()
        user_no = str(info.get("userNo") or "").strip()
        assert user_no, "登录态缺少 userNo，无法按创建人判断归属"

        report = check_scope(
            rows,
            label="我的订单",
            expected=user_no,
            fields=("creator", "creatorId", "userNo"),
            total=total,
        )
        print(f"\n[归属] {report.describe()}")

        if report.leaked:
            pytest.xfail(
                f"已知缺陷：我的订单返回他人订单。{report.describe()}；"
                f"当前 userNo={user_no}"
            )
        assert not report.leaked, report.describe()
