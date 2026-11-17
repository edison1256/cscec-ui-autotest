"""控制台「权限管理 → 客商管理」只读用例。

背景（2026-11-17 用户指正）：
  我此前记录「生产控制台没有客商管理菜单」是错的 —— 它在「权限管理」下，
  共 7 个子菜单。这条纠正来自用户截图，我此前只展开了一级菜单就下结论。

范围（按用户 2026-11-17 明确）：
  - 交互以**当前生产状态**为准，不按 PRD/大纲的理想态写断言
  - **不做**「已认证未开通企业」相关用例（生产暂无该数据样本）

因此本文件只覆盖：菜单完整性 + 7 个子菜单的页面可达与特征控件。
不涉及任何提交、审批、认证动作。
"""

from __future__ import annotations

import pytest

from pages.console.keshang_manage_page import (
    SUBMENU_MARKERS,
    SUBMENU_ROUTES,
    KeshangManagePage,
)

pytestmark = [
    pytest.mark.keshang,
    pytest.mark.console,
    pytest.mark.readonly,
]


@pytest.fixture(scope="function")
def keshang(logged_in_page) -> KeshangManagePage:
    return KeshangManagePage(logged_in_page)


class TestKeshangMenuStructure:
    """客商管理菜单本身。"""

    def test_ks_console_001_menu_complete(
        self, keshang: KeshangManagePage
    ) -> None:
        """KS-CONSOLE-001：权限管理下应有「客商管理」，且含 7 个子菜单。

        这条用例的存在本身就是一次纠错记录：曾误判生产无此菜单。
        """
        visible = keshang.visible_submenus()
        expected = tuple(SUBMENU_ROUTES)
        missing = [n for n in expected if n not in visible]
        assert not missing, (
            f"客商管理子菜单缺失: {missing}；实测可见={list(visible)}。"
            "若产品确已调整菜单，请同步更新 pages/console/keshang_manage_page.py"
        )

    def test_ks_console_002_menu_order(
        self, keshang: KeshangManagePage
    ) -> None:
        """KS-CONSOLE-002：子菜单顺序应与实测一致（认证审核在首位）。

        顺序变化通常意味着菜单重构，值得让用例提醒一次。
        """
        visible = keshang.visible_submenus()
        assert visible, "未读取到任何客商管理子菜单"
        assert visible[0] == "认证审核", (
            f"首个客商管理子菜单应为「认证审核」，实测为「{visible[0]}」"
        )


class TestKeshangSubPages:
    """7 个子菜单页面可达性与特征控件。"""

    @pytest.mark.parametrize("submenu", list(SUBMENU_ROUTES))
    def test_ks_console_10x_subpage(
        self, keshang: KeshangManagePage, submenu: str
    ) -> None:
        """KS-CONSOLE-101~107：逐个打开子菜单，校验路由与特征控件。"""
        state = keshang.open_submenu(submenu)

        assert state.route_ok, (
            f"「{submenu}」跳转路由不符：期望含 {SUBMENU_ROUTES[submenu]}，"
            f"实际 {state.url[:140]}"
        )
        assert not state.missing_markers, (
            f"「{submenu}」缺少特征控件 {list(state.missing_markers)}；"
            f"页面开头: {state.body_head[:200]}"
        )
        print(f"\n[{submenu}] url={state.url[:110]} 命中={state.markers_hit}")


class TestKeshangNoWriteBoundary:
    """只读边界守卫：这些页面存在写入口，但本套用例绝不触发。"""

    def test_ks_console_200_readonly_boundary(
        self, keshang: KeshangManagePage
    ) -> None:
        """KS-CONSOLE-200：客商管理页面的写操作按钮存在但不被点击。

        记录按钮存在性，作为「后续若要写用例需要先补清理机制」的提醒。
        """
        state = keshang.open_submenu("客商列表")
        body = state.body_head
        write_words = [w for w in ("新增", "编辑", "删除", "审核", "通过", "驳回") if w in body]
        print(f"\n[只读边界] 客商列表页存在的写操作词: {write_words}")
        # 只记录不失败：按钮文案随版本变化，不作为断言
        assert state.route_ok, "客商列表页未正确打开"
