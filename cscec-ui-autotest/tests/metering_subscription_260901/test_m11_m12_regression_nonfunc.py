"""M11: 已上线功能回归（P1）+ F12 + M12: 非功能与安全（P1）— 名义编号对齐."""

from __future__ import annotations

import time

import pytest

from tests.metering_subscription_260901.helpers import (
    CONSOLE_URL,
    WORKBENCH_URL,
    assert_entitlement_toggle,
    expand_first_row,
    click_when_visible,
    open_api_list_console,
    open_api_subscription_workbench,
    visible_texts,
    wait_list_ready,
)

pytestmark = [pytest.mark.readonly, pytest.mark.regression]


class TestM11Regression:
    """M11 已上线功能回归（M11.1-M11.3 为空壳小节，代表性回归面见下）."""

    @pytest.mark.console
    def test_m11_4_1__metering_statistics_overview(self, cs_page):
        """回归：计量统计-租户的订阅-订阅概览 / 租户的资源-资源概览 仍可达."""
        cs_page.goto("about:blank", wait_until="domcontentloaded", timeout=30000)
        cs_page.goto(CONSOLE_URL, wait_until="domcontentloaded", timeout=60000)
        cs_page.wait_for_load_state("networkidle", timeout=20000)
        assert click_when_visible(cs_page, "计量统计", timeout_ms=10000), (
            "计量统计菜单不可点"
        )
        time.sleep(2)
        assert click_when_visible(cs_page, "租户的订阅", timeout_ms=10000), (
            "租户的订阅分组不可点"
        )
        assert click_when_visible(cs_page, "订阅概览", timeout_ms=8000)
        cs_page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(2)
        body = visible_texts(cs_page)
        assert "订阅" in body, "订阅概览页面未渲染"

    @pytest.mark.console
    def test_m11_4_2__delivery_method_field(self, cs_page):
        """回归：服务组件列表交付方式 API/SDK 字段仍可展示."""
        open_api_list_console(cs_page)
        assert click_when_visible(cs_page, "组件列表", timeout_ms=8000)
        cs_page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(2)
        body = visible_texts(cs_page)
        assert "组件" in body, "组件列表页面未渲染"
        if "交付方式" not in body and "API" not in body and "SDK" not in body:
            pytest.skip(
                "ENV_LIMITED: 组件列表未检出交付方式/API/SDK 字样"
                "（可能无组件数据或列未展示），需组件数据复核"
            )

    @pytest.mark.console
    def test_m11_4_3__notification_scope_unchanged(self):
        """回归：小铃铛、消息、任务、通知数据范围不因 API 权益查询新增而变化."""
        pytest.skip(
            "手工协同：消息/通知数据范围对照需基线快照比对，"
            "建议随整体回归套件执行"
        )

    @pytest.mark.portal
    def test_m11_1_1__workbench_component_subscription_general(self, wb_page):
        """回归（M11.1 代表面）：工作台我的订阅-组件订阅 通用页面仍正常."""
        wb_page.goto("about:blank", wait_until="domcontentloaded", timeout=30000)
        wb_page.goto(WORKBENCH_URL, wait_until="domcontentloaded", timeout=60000)
        wb_page.wait_for_load_state("networkidle", timeout=20000)
        assert click_when_visible(wb_page, "我的订阅", timeout_ms=10000)
        assert click_when_visible(wb_page, "组件订阅", timeout_ms=6000)
        wb_page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(2)
        body = visible_texts(wb_page)
        assert "组件" in body, "组件订阅页面未渲染"

    @pytest.mark.console
    def test_m11_2_1__console_component_list_general(self, cs_page):
        """回归（M11.2 代表面）：控制台订阅服务-组件列表 通用页面仍正常."""
        open_api_list_console(cs_page)
        assert click_when_visible(cs_page, "组件列表", timeout_ms=8000)
        cs_page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(2)
        body = visible_texts(cs_page)
        assert "组件" in body, "组件列表页面未渲染"

    @pytest.mark.console
    def test_m11_3_1__order_management_reachable(self, cs_page):
        """回归（M11.3 代表面）：控制台订单中心-订单管理 仍可达且渲染."""
        cs_page.goto("about:blank", wait_until="domcontentloaded", timeout=30000)
        cs_page.goto(CONSOLE_URL, wait_until="domcontentloaded", timeout=60000)
        cs_page.wait_for_load_state("networkidle", timeout=20000)
        assert click_when_visible(cs_page, "订单中心", timeout_ms=10000)
        time.sleep(1.2)
        assert click_when_visible(cs_page, "订单管理", timeout_ms=8000)
        cs_page.wait_for_load_state("networkidle", timeout=15000)
        time.sleep(2)
        assert visible_texts(cs_page), "订单管理页面空白"

    @pytest.mark.portal
    def test_f12__removed_user_my_subscription(self):
        """F12：用户移除租户后查看我的订阅数据."""
        pytest.skip(
            "DATA_REQUIRED: 需要“先在租户内订阅→被移出租户→再查数据”的流程"
            "与账号编排，属流程型用例，列入手工协同"
        )


class TestM12NonFunctional:
    """M12 非功能与安全（可自动化面）."""

    @pytest.mark.portal
    def test_m12_1_1__large_data_query_performance(self):
        """性能：大数据量下 API 聚合列表查询响应满足系统约定."""
        pytest.skip(
            "手工协同（性能）：需大数据量构造与性能基线，"
            "当前 PRE 锚点数据量小（工作台 2 行），无性能意义"
        )

    @pytest.mark.portal
    def test_m12_1_2__multi_account_expand_performance(self):
        """性能：单父行多账户子表/抽屉展开不阻塞页面."""
        pytest.skip("手工协同（性能）：需单父行多账户数据")

    @pytest.mark.portal
    def test_m12_1_3__long_range_query_performance(self):
        """性能：长日期区间下接口用量与每日明细可用."""
        pytest.skip("手工协同（性能）：需长区间计量数据")

    @pytest.mark.portal
    def test_m12_1_4__export_capacity(self):
        """容量：多页数据导出全量结果不受分页影响."""
        pytest.skip("手工协同（容量）：需多页明细数据+文件校验")

    @pytest.mark.portal
    def test_m12_2_1__rapid_expand_collapse_stable(self, wb_page):
        """并发：连续快速点击查看/收起，页面状态稳定无错乱."""
        open_api_subscription_workbench(wb_page)
        assert_entitlement_toggle(wb_page)

    @pytest.mark.portal
    def test_m12_2_2__rapid_usage_toggle(self):
        """并发：连续快速点击查看用量/收起用量，接口用量不重复插入."""
        pytest.skip(
            "DATA_REQUIRED+ENV_LIMITED: 需接口用量数据核验重复插入；"
            "当前锚点已调用额=0"
        )

    @pytest.mark.console
    def test_m12_2_3__export_button_rapid_click(self):
        """并发：导出按钮连续点击不生成重复异常文件或页面不可用."""
        pytest.skip("手工协同：导出按钮未在当前页面暴露（见 M6.4/M6.5 差异）")

    @pytest.mark.console
    def test_m12_2_4__drawer_rapid_toggle_no_mixrow(self):
        """并发：抽屉开关过程中快速切换查询条件，不错行不残留."""
        pytest.skip("PENDING_IMPLEMENTATION: 需切换两个查询结果并断言抽屉归属，重复点查看不能替代")

    @pytest.mark.portal
    def test_m12_3_1__no_sensitive_credentials(self, wb_page, cs_page):
        """脱敏：工作台/控制台 API 权益页面不展示 AKSK/SecretKey 等敏感字段."""
        for page, navigate in ((wb_page, open_api_subscription_workbench), (cs_page, open_api_list_console)):
            navigate(page)
            assert expand_first_row(page), "权益子表展开失败，无法检查敏感字段"
            body = visible_texts(page).lower()
            for token in ("aksk", "secretkey", "secret_key", "accesskey"):
                assert token not in body, f"页面暴露敏感字段: {token}"

    @pytest.mark.portal
    def test_m12_3_2__bypass_tenant_data(self):
        """越权：低权限直访 URL/接口参数访问其他租户数据被拦截."""
        pytest.skip("ROLE_REQUIRED: 需低权限+跨租户账号对照（API 层专项更合适）")

    @pytest.mark.portal
    def test_m12_3_3__param_tamper_scope(self):
        """越权：篡改权益账户 ID/租户编码等参数仅返回授权范围数据."""
        pytest.skip("ROLE_REQUIRED: 参数篡改属接口安全专项，UI 黑盒单账号不可证")

    @pytest.mark.console
    def test_m12_3_4__export_scope_safety(self):
        """安全：导出文件只包含授权范围内明细数据."""
        pytest.skip(
            "手工协同：导出功能未在当前页面暴露且需文件内容校验（见 M6.4/M6.5）"
        )

    @pytest.mark.portal
    def test_m12_4_1__mobile_end(self):
        """兼容：移动端 —本轮范围外."""
        pytest.skip(
            "OUT_OF_SCOPE: 移动端需独立 UA/设备仿真专项，"
            "当前迭代页面为 PC 门户形态；建议列入移动端专项回归"
        )

    @pytest.mark.portal
    def test_m12_4_2__small_viewport_layout(self):
        """兼容：不同分辨率下表格/弹窗不遮挡关键操作（1366x768 抽检）."""
        pytest.skip("PENDING_IMPLEMENTATION: 需验证表格/弹窗关键操作的可见性及遮挡，读取文字不能证明布局正确")

    @pytest.mark.portal
    def test_m12_4_3__audit_trace(self):
        """审计：查看订单明细/导出/预警工单生成应留可追踪记录."""
        pytest.skip(
            "手工协同：需日志/审计系统配合查询，UI 黑盒不可证"
        )

    @pytest.mark.portal
    def test_m12_4_4__error_logging(self):
        """日志：查询/导出/计量异常/预警生成失败时有可定位日志或错误信息."""
        pytest.skip(
            "手工协同：需注入异常场景观察前端提示与后台日志，属专项"
        )


def _open_console(cs_page) -> None:
    open_api_list_console(cs_page)
    assert wait_list_ready(cs_page), "控制台 API列表 未渲染"
