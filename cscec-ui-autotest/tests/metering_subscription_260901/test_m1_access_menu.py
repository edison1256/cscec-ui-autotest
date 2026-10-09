"""M1: 入口与权限边界（P0）— 名义大纲编号对齐版.

PRE verified facts (2026-10-09, account 20431644 陈方达, portal role 普通成员):
- workbench menu tree (moduleCode 1899427585366003727) has NO 订阅中心 node;
  我的订阅 subtree contains API订阅.
- console menu tree (moduleCode 1899427585366003726) 订阅服务 contains
  应用列表/云产品列表/API列表/组件列表/数据资产列表.
"""

from __future__ import annotations

import pytest

from tests.metering_subscription_260901.helpers import (
    CONSOLE_URL,
    WORKBENCH_URL,
    click_when_visible,
    open_api_list_console,
    open_api_subscription_workbench,
    visible_texts,
    wait_list_ready,
)

pytestmark = [pytest.mark.readonly, pytest.mark.regression]


class TestM1WorkbenchEntry:
    """M1.1 工作台/控制台切换入口."""

    @pytest.mark.portal
    def test_m1_1_1__workbench_entry(self, wb_page):
        """工作台入口可达：登录后可打开工作台并展示我的订阅菜单组."""
        wb_page.goto("about:blank", wait_until="domcontentloaded", timeout=30000)
        wb_page.goto(WORKBENCH_URL, wait_until="domcontentloaded", timeout=60000)
        wb_page.wait_for_load_state("networkidle", timeout=20000)
        assert click_when_visible(wb_page, "我的订阅", timeout_ms=15000), (
            "工作台左侧菜单未出现“我的订阅”"
        )
        assert click_when_visible(wb_page, "API订阅", timeout_ms=6000), (
            "“我的订阅”下未展示 API订阅 子菜单"
        )

    @pytest.mark.console
    def test_m1_1_2__console_entry(self, cs_page):
        """控制台入口可达：展示订阅服务菜单及 API列表 叶子."""
        cs_page.goto("about:blank", wait_until="domcontentloaded", timeout=30000)
        cs_page.goto(CONSOLE_URL, wait_until="domcontentloaded", timeout=60000)
        cs_page.wait_for_load_state("networkidle", timeout=20000)
        assert click_when_visible(cs_page, "订阅服务", timeout_ms=15000), (
            "控制台左侧未出现“订阅服务”菜单组"
        )
        assert click_when_visible(cs_page, "API列表", timeout_ms=6000)


class TestM1WorkbenchMenuVisibility:
    """M1.2 工作台菜单可见性."""

    @pytest.mark.portal
    def test_m1_2_1__tenant_admin_subscription_center_visible(self, wb_page):
        """租户管理员访问“订阅中心-API列表”，期望菜单可见.

        当前账号门户角色=普通成员，实测工作台菜单树无“订阅中心”节点：
        无法区分“角色未授权”与“功能未部署”，需租户管理员账号复核。
        """
        wb_page.goto("about:blank", wait_until="domcontentloaded", timeout=30000)
        wb_page.goto(WORKBENCH_URL, wait_until="domcontentloaded", timeout=60000)
        wb_page.wait_for_load_state("networkidle", timeout=20000)
        body = visible_texts(wb_page)
        if "订阅中心" not in body:
            pytest.skip(
                "ROLE_REQUIRED: 当前账号（普通成员）菜单树无“订阅中心”，"
                "M2 模块入口缺失；需租户管理员/租户运营账号复核是否角色问题"
            )
        assert click_when_visible(wb_page, "订阅中心", timeout_ms=5000)

    @pytest.mark.portal
    def test_m1_2_2__no_permission_user_subscription_center_hidden(self, wb_page):
        """无订阅中心菜单权限用户，期望菜单不可见.

        当前账号（普通成员）实测菜单树无“订阅中心”→ 符合该用例期望；
        附带记录：需与 M1.2.1 管理员账号复核结果对照后定性。
        """
        wb_page.goto("about:blank", wait_until="domcontentloaded", timeout=30000)
        wb_page.goto(WORKBENCH_URL, wait_until="domcontentloaded", timeout=60000)
        wb_page.wait_for_load_state("networkidle", timeout=20000)
        body = visible_texts(wb_page)
        assert "订阅中心" not in body, (
            "普通成员账号可见“订阅中心”菜单（需核对角色配置是否符合预期）"
        )

    @pytest.mark.portal
    def test_m1_2_3__normal_user_my_subscription_visible_personal(self, wb_page):
        """普通用户访问“我的订阅-API订阅”，菜单可见（本人数据语义另见 M4.3.4）."""
        wb_page.goto("about:blank", wait_until="domcontentloaded", timeout=30000)
        wb_page.goto(WORKBENCH_URL, wait_until="domcontentloaded", timeout=60000)
        wb_page.wait_for_load_state("networkidle", timeout=20000)
        assert click_when_visible(wb_page, "我的订阅", timeout_ms=15000)
        assert click_when_visible(wb_page, "API订阅", timeout_ms=6000)

    @pytest.mark.portal
    def test_m1_2_4__normal_user_url_bypass_subscription_center(self, wb_page):
        """越权：普通用户 URL 直访订阅中心-API列表，期望被拦截."""
        pytest.skip(
            "ROLE_REQUIRED: 订阅中心路由未在当前账号菜单树下发，直链路由未知；"
            "需管理员账号取得路由后用普通账号做越权对照"
        )


class TestM1ConsoleMenuReadonly:
    """M1.3 控制台菜单与只读权限."""

    @pytest.mark.console
    def test_m1_3_1__console_subscription_service_leaves(self, cs_page):
        """平台运营视角：订阅服务五个列表叶子全部可见."""
        cs_page.goto("about:blank", wait_until="domcontentloaded", timeout=30000)
        cs_page.goto(CONSOLE_URL, wait_until="domcontentloaded", timeout=60000)
        cs_page.wait_for_load_state("networkidle", timeout=20000)
        assert click_when_visible(cs_page, "订阅服务", timeout_ms=15000)
        for leaf in ("应用列表", "云产品列表", "API列表", "组件列表", "数据资产列表"):
            assert click_when_visible(cs_page, leaf, timeout_ms=4000), f"叶子缺失: {leaf}"

    @pytest.mark.console
    def test_m1_3_2__unauthorized_console_blocked(self, cs_page):
        """非平台运营授权用户访问控制台订阅服务，期望被拦截."""
        pytest.skip(
            "ROLE_REQUIRED: 当前账号具备控制台角色（isExistConsoleRole=true），"
            "需非授权账号做拦截对照"
        )

    @pytest.mark.console
    def test_m1_3_3__console_api_list_readonly_actions(self, cs_page):
        """控制台 API列表 仅存在查看类操作，无续订/变配/增购/购买/编辑/删除."""
        open_api_list_console(cs_page)
        assert wait_list_ready(cs_page), "控制台 API列表 未渲染"
        body = visible_texts(cs_page)
        assert "查看" in body, "操作列未见“查看”入口"
        forbidden = [w for w in ("续订", "变配", "增购", "购买", "编辑", "删除") if w in body]
        assert not forbidden, f"控制台出现只读不允许的操作入口: {forbidden}"

    @pytest.mark.console
    def test_m1_3_4__workbench_user_console_bypass(self, wb_page):
        """越权：工作台用户直访控制台 API列表路由/接口，期望不能获取全租户数据."""
        pytest.skip(
            "ROLE_REQUIRED: 当前账号同时具备工作台与控制台角色，"
            "无法自证越权拦截；需纯工作台账号对照"
        )


class TestM1PageSplitRegression:
    """M1.4 页面拆分回归."""

    @pytest.mark.portal
    def test_m1_4_1__component_subscription_no_quota_fields(self, wb_page):
        """回归：工作台“组件订阅”页面不展示 API 权益专属额度字段."""
        wb_page.goto("about:blank", wait_until="domcontentloaded", timeout=30000)
        wb_page.goto(WORKBENCH_URL, wait_until="domcontentloaded", timeout=60000)
        wb_page.wait_for_load_state("networkidle", timeout=20000)
        assert click_when_visible(wb_page, "我的订阅", timeout_ms=15000)
        assert click_when_visible(wb_page, "组件订阅", timeout_ms=6000), (
            "组件订阅菜单不可点"
        )
        wb_page.wait_for_load_state("networkidle", timeout=15000)
        import time

        time.sleep(2)
        body = visible_texts(wb_page)
        quota_fields = [w for w in ("总可调用额", "剩余调用额") if w in body]
        assert not quota_fields, (
            f"组件订阅页面出现 API 权益专属字段: {quota_fields}（页面拆分回归风险）"
        )

    @pytest.mark.console
    def test_m1_4_2__console_component_list_regression(self, cs_page):
        """回归：控制台“组件列表”仍为通用组件订阅查询（未被 API 字段替换）."""
        open_api_list_console(cs_page)
        assert click_when_visible(cs_page, "组件列表", timeout_ms=8000), (
            "组件列表菜单不可点"
        )
        cs_page.wait_for_load_state("networkidle", timeout=15000)
        import time

        time.sleep(2)
        body = visible_texts(cs_page)
        assert "组件" in body, "组件列表页面未渲染"
        quota_fields = [w for w in ("总可调用额", "剩余调用额") if w in body]
        assert not quota_fields, f"控制台组件列表出现 API 专属字段: {quota_fields}"

    @pytest.mark.portal
    def test_m1_4_3__workbench_no_cross_tenant_console_data(self, wb_page):
        """回归：工作台 API订阅 列表仅本租户数据（不穿透全平台）."""
        open_api_subscription_workbench(wb_page)
        body = visible_texts(wb_page)
        cross = [t for t in ("架构管理部", "建证一体化", "中建云0731租户") if t in body]
        assert not cross, f"工作台出现全平台其他租户数据: {cross}"
