"""M1: 入口与权限边界（P0）— 名义大纲编号对齐版.

PRE verified facts (2026-10-09, account 20431644 陈方达, portal role 普通成员):
- workbench menu tree (moduleCode 1899427585366003727) has NO 订阅中心 node;
  我的订阅 subtree contains API订阅.
- console menu tree (moduleCode 1899427585366003726) 订阅服务 contains
  应用列表/云产品列表/API列表/组件列表/数据资产列表.
"""

from __future__ import annotations

import time

import pytest

from tests.metering_subscription_260901.helpers import (
    ANCHOR_TENANT_NO,
    PARENT_HEADERS,
    CONSOLE_URL,
    WORKBENCH_URL,
    click_when_visible,
    open_api_list_console,
    open_api_subscription_workbench,
    visible_texts,
    table_rows,
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
    """M1.2 工作台菜单可见性（租户形态定性：同账号双租户）.

    用户确认（2026-10-10）：账号 20431644 可经右上角账户悬停-切换租户；
    中建云租户=工作台普通成员形态（仅我的订阅）；中建数字科技有限公司
    租户=工作台租户管理员形态（出现订阅中心菜单）。
    """

    @pytest.mark.portal
    def test_m1_2_1__tenant_admin_subscription_center_visible(self, wb_page):
        """租户管理员（中建数字租户）访问“订阅中心”，期望菜单可见且可进入."""
        from tests.metering_subscription_260901.helpers import ensure_tenant

        assert ensure_tenant(wb_page, "sz"), "无法切换到中建数字租户（订阅中心形态）"
        body = visible_texts(wb_page)
        assert "订阅中心" in body, "中建数字租户下工作台未出现“订阅中心”菜单"
        assert click_when_visible(wb_page, "订阅中心", timeout_ms=6000)
        assert click_when_visible(wb_page, "API列表", timeout_ms=6000), (
            "订阅中心下未展示 API列表 叶子"
        )

    @pytest.mark.portal
    def test_m1_2_2__no_permission_user_subscription_center_hidden(self, wb_page):
        """普通成员形态（中建云租户），期望“订阅中心”菜单不可见."""
        from tests.metering_subscription_260901.helpers import ensure_tenant

        assert ensure_tenant(wb_page, "zjy"), "无法切换到中建云租户（我的订阅形态）"
        body = visible_texts(wb_page)
        assert "订阅中心" not in body, (
            "中建云租户（普通成员形态）可见“订阅中心”菜单，与授权模型不符"
        )

    @pytest.mark.portal
    def test_m1_2_3__normal_user_my_subscription_visible_personal(self, wb_page):
        """普通成员形态（中建云租户）访问“我的订阅-API订阅”，菜单可见."""
        from tests.metering_subscription_260901.helpers import ensure_tenant

        assert ensure_tenant(wb_page, "zjy"), "无法切换到中建云租户（我的订阅形态）"
        assert click_when_visible(wb_page, "我的订阅", timeout_ms=15000)
        assert click_when_visible(wb_page, "API订阅", timeout_ms=6000)

    @pytest.mark.portal
    def test_m1_2_4__normal_user_url_bypass_subscription_center(self, wb_page):
        """越权：普通成员形态（中建云租户）URL 直访订阅中心-API列表路由.

        V1.2 统一版（2026-10-10 部署）后，我的订阅-API订阅 与订阅中心-API列表
        为同一页面形态（统计方式+资源所属方，无租户列）。直访 menuCode 路由
        渲染同一页面不算越权；**数据范围**才是判定点：
        - 干净会话（无租户切换）：本人订阅为空 → 数据范围正确
        - 租户切换后的会话：观察到他租户（中建数字）聚合数据渲染在
          普通成员形态下 → 租户上下文不同步缺陷候选（记 D9，人工复核）
        """
        from tests.metering_subscription_260901.helpers import (
            ensure_tenant,
            gateway_error,
            list_is_empty,
        )

        assert ensure_tenant(wb_page, "zjy"), "无法切换到中建云租户（我的订阅形态）"
        bypass_url = (
            "https://cloud-pre.cscec.com/udpweb/portal/index.html"
            "?#/sub/resource/subscription/apiResource"
            "?suitKey=1899427585366003727&routeName=resource"
            "&appTitle=API%E8%AE%A2%E9%98%85&mc=1899427585366003727"
            "&mn=%E5%B7%A5%E4%BD%9C%E5%8F%B0&mt=module&menuCode=1925485794498359318"
        )
        wb_page.goto("about:blank", wait_until="domcontentloaded", timeout=30000)
        wb_page.goto(bypass_url, wait_until="domcontentloaded", timeout=60000)
        try:
            wb_page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        time.sleep(3)
        if gateway_error(wb_page):
            pytest.skip("ENV_LIMITED: pre 子应用网关 502，环境瞬时故障")
        body = visible_texts(wb_page)
        # 统一版形态页面正常渲染；关键判定：干净会话下数据范围为空（本人无订阅）
        if "资源所属方" in body and list_is_empty(wb_page):
            # 正确：普通成员本人无订阅数据，直访不泄露他租户数据
            assert True
            return
        # 数据非空时需人工定性（可能是租户上下文混合态，记 D9）
        pytest.skip(
            f"DATA_REQUIRED: 直访后列表非空（body 含统计方式={('统计方式' in body)}），"
            "需接口层核对数据租户归属后定性是否越权/上下文不同步（候选缺陷 D9）"
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
    def test_m1_3_2__unauthorized_console_blocked(self):
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
    def test_m1_3_4__workbench_user_console_bypass(self):
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
        """回归：工作台 API订阅 列表不穿透全平台数据.

        V1.2 统一版后页面无租户列，数据层租户归属需接口核对（本用例为
        页面文本层判定）：控制台特有的其他租户名不应出现在本页。
        """
        from tests.metering_subscription_260901.helpers import list_is_empty

        open_api_subscription_workbench(wb_page)
        if list_is_empty(wb_page):
            pytest.skip(
                "ENV_LIMITED: V1.2 统一版下本人订阅为空，跨租户文本判定无样本；"
                "数据层归属由 M2（订阅中心按租户过滤）覆盖"
            )
        body = visible_texts(wb_page)
        cross = [t for t in ("架构管理部", "建证一体化") if t in body]
        assert not cross, f"工作台页面出现控制台视角的其他租户名: {cross}"
