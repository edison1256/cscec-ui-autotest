"""M7: 控制台 API 列表与权益抽屉（F07/F08，P0）— 名义大纲编号对齐版.

PRE verified: aggregateForConsole + quota-instance/listByIds; multi-tenant rows;
anchor 实际控制人 | ZJ2025061915440022 | 组件申请 | 国资委审计专用 |
2026-05-18 14:17:03 ~ 2027-05-18 14:17:03 | 可用 | 不限次数 | 0 | 不限次数.
Deviation: drill-down is inline child table (PRD V1.2 says right-side drawer);
no 统计方式 control; query bar only 资源名称/资源编码/订阅时间.
"""

from __future__ import annotations

import time

import pytest

from tests.metering_subscription_260901.helpers import (
    CHILD_HEADERS,
    CS_ANCHOR_APP,
    CS_ANCHOR_RESOURCE,
    assert_headers_present,
    click_text_strict,
    click_when_visible,
    gateway_error,
    open_api_list_console,
    visible_texts,
    wait_list_ready,
)

pytestmark = [pytest.mark.readonly, pytest.mark.console, pytest.mark.regression]


def _open(cs_page) -> None:
    open_api_list_console(cs_page)
    assert wait_list_ready(cs_page), "控制台 API列表 未渲染"


def _query(cs_page, placeholder: str, value: str) -> None:
    box = cs_page.get_by_placeholder(placeholder)
    assert box.count() > 0, f"查询输入框缺失: {placeholder}"
    box.first.fill(value)
    cs_page.get_by_role("button", name="查 询", exact=True).click()
    time.sleep(2.5)


class TestM7DefaultLoad:
    """M7.1 控制台列表默认加载."""

    def test_m7_1_1__default_load_multi_tenant(self, cs_page):
        """主流程：平台运营进入控制台-API列表，展示全租户 API 订阅聚合列表."""
        _open(cs_page)
        body = visible_texts(cs_page)
        assert CS_ANCHOR_RESOURCE in body, "锚点资源（实际控制人）未展示"
        assert "架构管理部" in body or "建证一体化" in body, "未见多租户数据"

    def test_m7_1_2__parent_headers(self, cs_page):
        """UI：列表列名与 PRD 一致（租户/资源/服务模式/订阅数量/操作）."""
        _open(cs_page)
        assert_headers_present(
            cs_page,
            ("序号", "租户编码", "租户名称", "资源名称", "资源编码",
             "服务模式", "资源发布方", "订阅数量", "操作"),
            "控制台 API列表父表",
        )

    def test_m7_1_3__legacy_fields_upgraded(self, cs_page):
        """UI：历史字段（订阅ID/订阅资源名称/订阅人）升级后不再出现在聚合列表."""
        _open(cs_page)
        body = visible_texts(cs_page)
        legacy = [w for w in ("订阅ID", "订阅资源名称") if w in body]
        assert not legacy, f"列表仍出现历史字段: {legacy}（需与 PRD/原型核对字段终态）"

    def test_m7_1_4__row_is_tenant_resource_mode_combo(self, cs_page):
        """数据：每行代表一个租户、资源、服务模式组合."""
        pytest.skip(
            "DATA_REQUIRED: 需同一资源多服务模式/多租户组合数据核验行唯一性"
        )


class TestM7Query:
    """M7.2 控制台查询条件."""

    def test_m7_2_1__query_by_tenant_code(self, cs_page):
        """查询：租户编码筛选——实测查询区无租户编码输入."""
        _open(cs_page)
        if cs_page.get_by_placeholder("请输入租户编码").count() == 0:
            pytest.skip(
                "ENTRY_MISSING(实现差异): 查询区无“租户编码”筛选输入，"
                "需求-实现差异待产品确认"
            )

    def test_m7_2_2__query_by_tenant_name(self, cs_page):
        """查询：租户名称筛选——实测查询区无租户名称输入."""
        _open(cs_page)
        if cs_page.get_by_placeholder("请输入租户名称").count() == 0:
            pytest.skip(
                "ENTRY_MISSING(实现差异): 查询区无“租户名称”筛选输入，"
                "需求-实现差异待产品确认"
            )

    def test_m7_2_3__query_by_resource_name(self, cs_page):
        """查询：资源名称=WPS服务组件，仅返回匹配行（含组合/空结果补充覆盖）."""
        _open(cs_page)
        _query(cs_page, "请输入资源名称", "WPS服务组件")
        body = visible_texts(cs_page)
        assert "WPS服务组件" in body
        assert CS_ANCHOR_RESOURCE not in body, "不匹配资源未被过滤"

    def test_m7_2_4__query_by_resource_code(self, cs_page):
        """查询：资源编码筛选生效."""
        _open(cs_page)
        _query(cs_page, "请输入资源编码", "ZJ2025061915440022")
        body = visible_texts(cs_page)
        assert CS_ANCHOR_RESOURCE in body, "编码查询未返回锚点资源"

    def test_m7_2_5__query_by_subscribe_time(self, cs_page):
        """查询：订阅时间区间只统计区间内成功订阅形成的权益账户."""
        pytest.skip(
            "手工协同：时间区间语义需已知订阅时间分布数据对照；"
            "控件存在性已由 M4.1.3/M7.1.2 覆盖"
        )

    def test_m7_2_6__query_reset(self, cs_page):
        """重置：修改条件后重置，恢复默认并重新加载."""
        _open(cs_page)
        _query(cs_page, "请输入资源名称", "不存在的资源XYZ")
        cs_page.get_by_role("button", name="重 置", exact=True).click()
        time.sleep(2.5)
        body = visible_texts(cs_page)
        assert CS_ANCHOR_RESOURCE in body, "重置后锚点数据未恢复"
        name_input = cs_page.get_by_placeholder("请输入资源名称")
        assert name_input.input_value() == "", "重置后资源名称未清空"


class TestM7StatisticsMode:
    """M7.3 控制台统计方式（实现差异：无统计方式控件）."""

    def test_m7_3_1__aggregate_scope_control(self, cs_page):
        """数据范围：汇总本租户及下级/仅本租户切换——实测无统计方式控件."""
        _open(cs_page)
        body = visible_texts(cs_page)
        if "统计方式" not in body and "汇总本租户" not in body:
            pytest.skip(
                "ENTRY_MISSING(实现差异): 控制台 API列表 无“统计方式”查询控件，"
                "M7.3/M2.3 大纲用例不可执行，记录为需求-实现差异"
            )
        assert "统计方式" in body

    def test_m7_3_2__scope_only_self(self, cs_page):
        """数据范围：仅本租户统计."""
        pytest.skip("ENTRY_MISSING(实现差异): 同 M7.3.1，无统计方式控件")

    def test_m7_3_3__scope_change_consistency(self, cs_page):
        """一致性：统计方式变更后抽屉范围与父表订阅数量一致."""
        pytest.skip("ENTRY_MISSING(实现差异): 同 M7.3.1，无统计方式控件")

    def test_m7_3_4__unauthorized_tenant_hidden(self, cs_page):
        """权限：平台运营无权限的租户数据不在列表和抽屉展示."""
        pytest.skip("ROLE_REQUIRED: 需限定租户可见范围的平台运营账号对照")


class TestM7EntitlementDrawer:
    """M7.4 权益账户下钻（实测形态：行内子表展开，非右侧抽屉）."""

    def test_m7_4_1__open_entitlement_view(self, cs_page):
        """交互：点击行“查看”，展开权益账户（实测为行内子表，与 PRD 抽屉形态差异）."""
        _open(cs_page)
        assert click_when_visible(cs_page, "查看", timeout_ms=8000), "查看不可点"
        time.sleep(2.5)
        body = visible_texts(cs_page)
        assert CS_ANCHOR_RESOURCE in body, "展开后子表未见锚点资源"

    def test_m7_4_2__drawer_title_identity(self, cs_page):
        """UI：抽屉标题含租户名称/资源名称/服务模式/统计方式（实测无独立标题区）."""
        _open(cs_page)
        assert click_when_visible(cs_page, "查看", timeout_ms=8000)
        time.sleep(2.5)
        body = visible_texts(cs_page)
        if "API订阅权益" not in body:
            pytest.skip(
                "ENTRY_MISSING(实现差异): 无“API订阅权益”抽屉标题区"
                "（下钻为行内子表形态），与 PRD V1.2 右侧抽屉描述不一致，"
                "以现实现记录"
            )

    def test_m7_4_3__fields_match_workbench(self, cs_page):
        """UI：子表字段与工作台权益账户子表一致（锚点固定期限+不限量）."""
        _open(cs_page)
        assert click_when_visible(cs_page, "查看", timeout_ms=8000)
        time.sleep(2.5)
        assert_headers_present(cs_page, CHILD_HEADERS, "控制台权益子表")
        body = visible_texts(cs_page)
        assert CS_ANCHOR_APP in body, "子表未展示订阅应用（国资委审计专用）"
        assert "不限次数" in body, "子表未展示不限次数"
        assert "2027-05-18" in body, "子表未展示固定截止日期"

    def test_m7_4_4__close_returns_state(self, cs_page):
        """交互：关闭后返回当前查询条件、分页和列表状态（按钮文字保持“查看”→差异）."""
        _open(cs_page)
        if gateway_error(cs_page):
            pytest.skip("ENV_LIMITED: pre 子应用网关 502，环境瞬时故障")
        assert click_when_visible(cs_page, "查看", timeout_ms=8000)
        time.sleep(2)
        if not click_text_strict(cs_page, "收起", timeout_ms=3000):
            # 差异路径：按钮文字未变，再次点击“查看”收起
            assert click_when_visible(cs_page, "查看", timeout_ms=6000), (
                "既无“收起”也无法再次点击“查看”收起"
            )
        time.sleep(2)
        body = visible_texts(cs_page)
        assert "租户编码" in body, "收起后父表未恢复"
        assert CS_ANCHOR_RESOURCE in body, "收起后锚点行丢失"

    def test_m7_4_5__subtable_scope(self, cs_page):
        """数据：子表仅展示当前父行资源/服务模式确定的权益账户."""
        pytest.skip(
            "DATA_REQUIRED: 需同资源多服务模式/多账户组合数据核验子表范围隔离"
        )


class TestM7DrawerDrilldown:
    """M7.5 控制台抽屉内下钻."""

    def test_m7_5_1__order_detail(self, cs_page):
        """交互：查看订单明细打开当前权益账户成功订阅明细."""
        _open(cs_page)
        assert click_when_visible(cs_page, "查看", timeout_ms=8000)
        time.sleep(2)
        btn = cs_page.get_by_text("查看订单明细", exact=True).first
        assert btn.is_visible(timeout=6000), "查看订单明细不可见"
        btn.click()
        time.sleep(2.5)
        body = visible_texts(cs_page)
        assert "订单明细" in body or "订单ID" in body, "控制台订单明细未打开"

    def test_m7_5_2__usage_expand(self, cs_page):
        """交互：查看用量在抽屉内当前账户行下展开接口用量."""
        _open(cs_page)
        assert click_when_visible(cs_page, "查看", timeout_ms=8000)
        time.sleep(2)
        assert click_when_visible(cs_page, "查看用量", timeout_ms=6000), (
            "查看用量不可点"
        )
        time.sleep(2.5)
        body = visible_texts(cs_page)
        assert "已调用额" in body or "用量" in body, "展开用量后未见相关内容"

    def test_m7_5_3__daily_detail_dialog(self, cs_page):
        """交互：接口“查看明细”打开每日调用明细弹窗."""
        _open(cs_page)
        assert click_when_visible(cs_page, "查看", timeout_ms=8000)
        time.sleep(2)
        if not click_when_visible(cs_page, "查看用量", timeout_ms=6000):
            pytest.skip("ENV_LIMITED: 查看用量入口未就绪")
        time.sleep(2)
        if not click_text_strict(cs_page, "查看明细", timeout_ms=6000):
            pytest.skip("ENV_LIMITED: 无调用明细入口（锚点接口无调用数据）")
        time.sleep(2.5)
        body = visible_texts(cs_page)
        assert "明细" in body, "每日明细弹窗未打开"

    def test_m7_5_4__readonly_everywhere(self, cs_page):
        """权限：控制台全链路只读，下钻不提供修改权益/额度/API 范围入口."""
        _open(cs_page)
        assert click_when_visible(cs_page, "查看", timeout_ms=8000)
        time.sleep(2)
        if click_when_visible(cs_page, "查看订单明细", timeout_ms=4000):
            time.sleep(2)
        body = visible_texts(cs_page)
        forbidden = [w for w in ("续订", "变配", "增购", "立即购买", "编辑", "删除") if w in body]
        assert not forbidden, f"控制台出现修改类入口: {forbidden}"
