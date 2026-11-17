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


class TestWorkbenchListScope:
    """个人工作台各列表的归属范围（路径待通，结论待重验）。"""

    def test_dh_scope_101_subscribed_orders(
        self, workbench: PersonalWorkbenchPage
    ) -> None:
        """DH-SCOPE-101：被订阅的订单的数据量必须落在本租户量级。

        实测（2026-11-17，PROD，正确工作台套件 suitKey=1899427585366003727）：
            接口 POST /irp-api/irp-portal-workbench/order/applyPage
            total=13，creator 只有 3 人（均为本租户成员）
        对照组（错误做法：直链 suitKey=portal）看到的是另一个套件的
            workbench/rsc/app/apply/history/list，828 条 / 26 租户 / 57 用户
            —— 那是直链绕过视图选择的结果，不是业务数据。

        该接口**不返回 tenantNo**，无法按租户严格判归属，因此改用「量级守门」：
        一旦数据范围重新扩大到全平台量级（>200），本用例立即失败。
        """
        workbench.open_card("被订阅的订单", wait_ms=8000)
        total = workbench.read_list_total()
        rows = workbench.count_visible_rows()
        print(f"\n[量级] 页面总条数={total}，当前页行数={rows}（基线 13，上限 200）")

        if total < 0:
            try:
                tail = workbench.page.locator("body").inner_text()[-400:]
            except Exception:
                tail = ""
            raise AssertionError(
                "未能从页面读取总条数（实测文案形如「第 1-13 条/总共 13 条」，"
                f"正则未命中）。页面末尾 400 字: {tail}"
            )
        assert total <= 200, (
            f"被订阅的订单页面显示 {total} 条，超出本租户量级（基线 13）。"
            "疑似数据范围未按租户收口，或进入了错误的套件视图"
            "（直链 suitKey=portal 时该页面曾出现 828 条 / 26 租户）"
        )
        # 表格实现可能不是 ant-table，行数为 0 时只做提示，不判失败；
        # 本用例的核心是「数据量是否落在本租户量级」。
        if rows == 0:
            print(
                "  [提示] 未通过 tbody tr.ant-table-row 匹配到行，"
                "表格结构可能不同；总数口径已取到，不影响量级判定"
            )

    @pytest.mark.skip(
        reason=(
            "接口待在工作台套件（suitKey=1899427585366003727）下重新确认。"
            "此前记录的 cloud/applyList、workbench/rsc/data/apply/history/list、"
            "order/page 都来自直链 suitKey=portal 的另一套件，不可沿用。"
            "参照 DH-SCOPE-101 的做法：先抓全部响应反查真实接口，再做量级守门。"
        )
    )
    def test_dh_scope_102_cloud_subscription(
        self, workbench: PersonalWorkbenchPage
    ) -> None:
        """DH-SCOPE-102：云产品订阅只应包含当前账号的数据。"""
        _assert_tenant_scoped(
            workbench,
            label="云产品订阅",
            entry_label="云产品订阅",
            api_hint="cloud/applyList",  # 待在工作台套件下复核
        )

    @pytest.mark.skip(
        reason=(
            "接口待在工作台套件（suitKey=1899427585366003727）下重新确认。"
            "此前记录的 cloud/applyList、workbench/rsc/data/apply/history/list、"
            "order/page 都来自直链 suitKey=portal 的另一套件，不可沿用。"
            "参照 DH-SCOPE-101 的做法：先抓全部响应反查真实接口，再做量级守门。"
        )
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

    @pytest.mark.skip(
        reason=(
            "接口待在工作台套件（suitKey=1899427585366003727）下重新确认。"
            "此前记录的 cloud/applyList、workbench/rsc/data/apply/history/list、"
            "order/page 都来自直链 suitKey=portal 的另一套件，不可沿用。"
            "参照 DH-SCOPE-101 的做法：先抓全部响应反查真实接口，再做量级守门。"
        )
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
