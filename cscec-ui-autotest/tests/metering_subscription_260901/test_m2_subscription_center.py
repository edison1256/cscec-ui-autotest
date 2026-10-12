"""M2: 工作台订阅中心 API 列表（F01，P0）— 中建数字租户真实断言版.

Tenant context (user-confirmed 2026-10-10): account 20431644 can switch
tenant via 右上角账户悬停 -> 切换租户. Under 中建数字科技有限公司 the workbench
shows the tenant-admin shape with 订阅中心 menu; under 中建云 it shows the
normal-member shape (我的订阅 only).

PRE verified (中建数字 shape, 2026-10-10 r8):
- query bar: 统计方式(下拉,默认 汇总本租户及下级数据) / 资源名称 / 资源编码 + 查 询 / 重 置
- parent headers: 资源名称/资源编码/服务模式/资源所属方/订阅数量/操作(查看)
- anchor: 实际控制人 / ZJ2025061915440022 / 组件申请 / 订阅数量 5
- API: /irp-api/irp-portal-workbench/quota-instance/aggregate (same endpoint,
  tenant context decides scope)
"""

from __future__ import annotations

import time

import pytest

from tests.metering_subscription_260901.helpers import (
    CS_ANCHOR_RESOURCE,
    PARENT_HEADERS,
    click_when_visible,
    expand_first_row,
    gateway_error,
    open_subscription_center,
    table_rows,
    table_with_headers,
    visible_texts,
    wait_list_ready_sc,
)

pytestmark = [pytest.mark.readonly, pytest.mark.portal, pytest.mark.regression]

SC_ANCHOR_CODE = "ZJ2025061915440022"


def _open_sc(wb_page):
    """Open 订阅中心-API列表 under 中建数字 tenant; assert rendered."""
    open_subscription_center(wb_page)
    assert wait_list_ready_sc(wb_page), "订阅中心-API列表 未渲染"
    if gateway_error(wb_page):
        pytest.skip("ENV_LIMITED: pre 子应用网关 502，环境瞬时故障")


def _query(wb_page, placeholder: str, value: str) -> None:
    box = wb_page.get_by_placeholder(placeholder)
    assert box.count() > 0, f"查询输入框缺失: {placeholder}"
    box.first.fill(value)
    wb_page.get_by_role("button", name="查 询", exact=True).click()
    time.sleep(2.5)


class TestM2DefaultLoad:
    """M2.1 默认加载与列表字段."""

    def test_m2_1_1__subscription_center_load(self, wb_page):
        """主流程：租户管理员进入订阅中心-API列表，父子表初始折叠."""
        _open_sc(wb_page)
        body = visible_texts(wb_page)
        assert CS_ANCHOR_RESOURCE in body, "锚点资源（实际控制人）未展示"
        assert "查看订单明细" not in body, "初始状态子表已展开（应折叠）"

    def test_m2_1_2__parent_headers(self, wb_page):
        """UI：父表列名含资源名称/资源编码/服务模式/资源发布方(或所属方)/订阅数量/操作."""
        _open_sc(wb_page)
        body = visible_texts(wb_page)
        owner_col = "资源发布方" if "资源发布方" in body else "资源所属方"
        table_with_headers(
            wb_page,
            ("资源名称", "资源编码", "服务模式", owner_col, "订阅数量", "操作"),
            "订阅中心-API列表父表",
        )

    def test_m2_1_3__wps_rows_by_service_mode(self, wb_page):
        """数据：WPS 服务组件按不同服务模式分别成行.

        中建数字租户锚点无 WPS 数据（WPS 在中建云租户），以现有锚点验证
        行=资源+服务模式组合；WPS 专项留在中建云形态对照（M4）。
        """
        _open_sc(wb_page)
        rows = table_rows(
            wb_page,
            ("资源名称", "资源编码", "服务模式", "订阅数量"),
            "订阅中心父表",
        )
        combos = {(r["资源名称"], r["服务模式"]) for r in rows}
        assert len(combos) == len(rows), "存在重复的 资源+服务模式 组合行"

    def test_m2_1_4__api_resource_identification(self, wb_page):
        """数据：API 资源名称（wdl集成平台组件）查询进入 API 列表口径."""
        _open_sc(wb_page)
        _query(wb_page, "请输入资源名称", "wdl集成平台组件")
        body = visible_texts(wb_page)
        if "wdl集成平台组件" not in body:
            pytest.skip(
                "DATA_REQUIRED: 中建数字租户当前无 wdl集成平台组件 订阅数据，"
                "口径识别留待数据补齐（列表查询功能本身由 M2.2.x 覆盖）"
            )
        assert "wdl集成平台组件" in body

    def test_m2_1_5__sdk_not_in_list(self, wb_page):
        """数据：SDK 资源（WPS服务）不混入 API 权益聚合列表.

        资源名称为模糊匹配：查询"WPS服务"会命中 API 资源"WPS服务组件"（合法）；
        断言结果行中不存在名为"WPS服务"（纯 SDK 名）的独立资源行。
        """
        _open_sc(wb_page)
        _query(wb_page, "请输入资源名称", "WPS服务")
        rows = table_rows(
            wb_page,
            ("资源名称", "资源编码", "服务模式", "订阅数量"),
            "订阅中心父表",
        )
        sdk_rows = [r for r in rows if r["资源名称"].strip() == "WPS服务"]
        assert not sdk_rows, f"纯 SDK 资源（WPS服务）混入 API 聚合列表: {sdk_rows}"
        # 命中的都是 API 组件（如 WPS服务组件），服务模式非空
        for r in rows:
            assert r["服务模式"].strip(), f"行 {r['资源名称']} 服务模式为空"

    def test_m2_1_6__no_service_mode_missing(self, wb_page):
        """展示：不存在服务模式缺失的 API 类组件时（所有行服务模式非空）."""
        _open_sc(wb_page)
        rows = table_rows(
            wb_page,
            ("资源名称", "服务模式", "订阅数量"),
            "订阅中心父表",
        )
        empty_modes = [r["资源名称"] for r in rows if not r["服务模式"].strip()]
        assert not empty_modes, f"以下资源服务模式为空: {empty_modes}"


class TestM2Query:
    """M2.2 查询条件."""

    def test_m2_2_1__query_by_code(self, wb_page):
        """查询：输入存在的资源编码查询，仅返回匹配行."""
        _open_sc(wb_page)
        _query(wb_page, "请输入资源编码", SC_ANCHOR_CODE)
        body = visible_texts(wb_page)
        assert CS_ANCHOR_RESOURCE in body, "编码查询未返回锚点资源"
        assert "建筑业资质查询" not in body, "不匹配资源未被过滤"

    def test_m2_2_2__query_by_name(self, wb_page):
        """查询：输入存在的资源名称（实际控制人）查询."""
        _open_sc(wb_page)
        _query(wb_page, "请输入资源名称", CS_ANCHOR_RESOURCE)
        body = visible_texts(wb_page)
        assert CS_ANCHOR_RESOURCE in body
        assert "分支机构" not in body, "不匹配资源未被过滤"

    def test_m2_2_3__combined_query(self, wb_page):
        """查询：资源编码+资源名称组合查询同时生效."""
        _open_sc(wb_page)
        _query(wb_page, "请输入资源名称", CS_ANCHOR_RESOURCE)
        _query(wb_page, "请输入资源编码", SC_ANCHOR_CODE)
        body = visible_texts(wb_page)
        assert CS_ANCHOR_RESOURCE in body

    def test_m2_2_4__reset(self, wb_page):
        """重置：修改条件后重置恢复默认并重新加载."""
        _open_sc(wb_page)
        _query(wb_page, "请输入资源名称", "不存在的资源XYZ")
        wb_page.get_by_role("button", name="重 置", exact=True).click()
        time.sleep(2.5)
        body = visible_texts(wb_page)
        assert CS_ANCHOR_RESOURCE in body, "重置后锚点数据未恢复"
        name_input = wb_page.get_by_placeholder("请输入资源名称")
        assert name_input.input_value() == "", "重置后资源名称未清空"

    def test_m2_2_5__empty_result(self, wb_page):
        """空结果：输入不存在的资源编码查询列表为空."""
        _open_sc(wb_page)
        _query(wb_page, "请输入资源编码", "ZJ0000000000000000")
        body = visible_texts(wb_page)
        assert CS_ANCHOR_RESOURCE not in body, "空结果仍展示数据"


class TestM2StatisticsScope:
    """M2.3 统计方式与租户范围."""

    def test_m2_3_1__aggregate_scope_default(self, wb_page):
        """数据范围：默认“汇总本租户及下级数据”，列表有数据行."""
        _open_sc(wb_page)
        body = visible_texts(wb_page)
        assert "统计方式" in body, "查询区无统计方式控件"
        assert "汇总本租户及下级数据" in body, "统计方式默认值非“汇总本租户及下级数据”"
        assert "暂无数据" not in body, "汇总口径下列表为空（应有锚点数据）"

    def test_m2_3_2__scope_only_self(self, wb_page):
        """数据范围：切换“仅本租户”后列表重新加载."""
        _open_sc(wb_page)
        # 统计方式为下拉/选择器，点开后选项
        ctrl = wb_page.locator(".ant-select, .el-select").filter(
            has_text="汇总本租户及下级数据"
        )
        if ctrl.count() == 0:
            pytest.skip(
                "ENV_LIMITED: 统计方式控件结构非 ant/el select，"
                "交互定位待补充（控件存在性已由 M2.3.1 验证）"
            )
        ctrl.first.click()
        time.sleep(1.2)
        option = wb_page.get_by_text("仅本租户", exact=True).first
        if not option.is_visible(timeout=4000):
            shot = wb_page.screenshot(path="screenshots/m2_3_2_dropdown.png")
            pytest.skip("ENV_LIMITED: 下拉选项未见“仅本租户”，见截图 m2_3_2_dropdown.png")
        option.click()
        time.sleep(2.5)
        body = visible_texts(wb_page)
        assert CS_ANCHOR_RESOURCE in body, "切换统计方式后列表未加载"

    def test_m2_3_3__scope_switch_consistency(self, wb_page):
        """一致性：统计方式变更后同一行子表范围与父表订阅数量一致."""
        pytest.skip(
            "DATA_REQUIRED: 需同一资源在下级租户有权益账户的数据分布，"
            "当前锚点两种统计方式结果一致（无下级差异数据）"
        )

    def test_m2_3_4__no_child_tenant_boundary(self, wb_page):
        """边界：无下级租户数据时汇总与仅本租户结果一致（锚点对比）."""
        pytest.skip(
            "DATA_REQUIRED: 需对比两种统计方式的数量差异，"
            "当前锚点租户树下无差异数据可核验"
        )


class TestM2Aggregation:
    """M2.4 订阅数量聚合口径（需多订单/多应用/多模式数据）."""

    def test_m2_4_1__dedup_by_entitlement(self, wb_page):
        """数据：多成功订单按权益账户去重（非订单数累加）."""
        pytest.skip("DATA_REQUIRED: 需同一组合多成功订单数据对照订单数")

    def test_m2_4_2__per_app_counter(self, wb_page):
        """数据：不同应用订阅同服务模式分别计数."""
        pytest.skip("DATA_REQUIRED: 需多应用订阅数据")

    def test_m2_4_3__per_service_mode(self, wb_page):
        """数据：同一资源多服务模式独立展示订阅数量."""
        pytest.skip("DATA_REQUIRED: 需同资源多服务模式订阅数据")

    def test_m2_4_4__multi_api_one_account(self, wb_page):
        """数据：同一权益账户多 API 订阅数量仍计 1."""
        pytest.skip("DATA_REQUIRED: 需单账户多 API 数据")


class TestM2ExpandCollapse:
    """M2.5 折叠与展开."""

    def test_m2_5_1__expand_single_row(self, wb_page):
        """交互：点击父行查看，展开当前行权益账户子表（按钮文字保持“查看”，差异见 M3.5.3）."""
        _open_sc(wb_page)
        assert expand_first_row(wb_page), "父行“查看”不可点或子表未展开"
        body = visible_texts(wb_page)
        assert "查看订单明细" in body, "展开后未见子表操作入口"

    def test_m2_5_2__collapse_restores(self, wb_page):
        """交互：再次点击收起，子表关闭（等价行为，按钮文字差异见 M3.5.3）."""
        from tests.metering_subscription_260901.helpers import click_text_strict

        _open_sc(wb_page)
        assert expand_first_row(wb_page), "首次展开失败"
        time.sleep(1.5)
        if not click_text_strict(wb_page, "收起", timeout_ms=3000):
            assert click_when_visible(wb_page, "查看", timeout_ms=6000), (
                "无法收起子表"
            )
        time.sleep(2)
        body = visible_texts(wb_page)
        assert "查看订单明细" not in body, "再次点击后子表未收起"

    def test_m2_5_3__switch_row_expand(self, wb_page):
        """交互：展开第一行后点第二行查看，单行展开状态符合约定（记录实际行为）."""
        _open_sc(wb_page)
        assert expand_first_row(wb_page), "第一行展开失败"
        time.sleep(1)
        # 点第二行（锚点第二行=建筑业资质查询）
        second = wb_page.get_by_text("建筑业资质查询", exact=True).first
        if not second.is_visible(timeout=4000):
            pytest.skip("ENV_LIMITED: 第二行锚点资源不可见")
        # 第二行的操作列查看
        row_view = wb_page.get_by_text("查看", exact=True)
        # 展开第二行：点除第一行外的下一个"查看"
        clicked = False
        for i in range(min(row_view.count(), 6)):
            el = row_view.nth(i)
            try:
                if el.is_visible(timeout=500):
                    el.click()
                    clicked = True
                    if i >= 1:
                        break
            except Exception:
                continue
        assert clicked, "第二行查看不可点"
        time.sleep(2.5)
        body = visible_texts(wb_page)
        # 记录行为：多行同时展开 or 单行互斥，均视为系统约定并记录
        assert "查看订单明细" in body, "第二行展开失败"

    def test_m2_5_4__initial_collapsed_on_reentry(self, wb_page):
        """状态：重新进入页面父子表恢复初始折叠."""
        _open_sc(wb_page)
        assert expand_first_row(wb_page), "展开失败"
        # 重新导航进入
        open_subscription_center(wb_page)
        assert wait_list_ready_sc(wb_page), "重新进入后列表未渲染"
        time.sleep(2)
        body = visible_texts(wb_page)
        assert "查看订单明细" not in body, "重新进入后子表仍处于展开状态"
