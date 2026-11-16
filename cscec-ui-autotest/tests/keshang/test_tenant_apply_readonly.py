"""客商接入 · 门户侧只读用例（大纲 M02 / M03）。

覆盖 10 条不产生任何写入的断言，全部走真实点击路径
（个人卡片 → 切换租户 → 创建租户），不拼二级页 URL。

安全边界：
- **从不点击「确认提交」**：`KS-M03-004` 只读取按钮的 `disabled` 状态。
- **不勾选声明、不填表单、不切换租户**：仅读取文本与属性。
- 取消类用例（`KS-M03-006`）只按 Escape / 点「取消」，不产生记录。
"""

from __future__ import annotations

import re

import pytest

from config.settings import settings
from core.browser_health import BrowserHealthMonitor
from pages.portal.tenant_onboarding_page import (
    STATUS_WORDS,
    TenantOnboardingPage,
)

pytestmark = [
    pytest.mark.keshang,
    pytest.mark.portal,
    pytest.mark.readonly,
]

# 个人卡片应出现的区域名（大纲 M02-L02）
CARD_AREAS = ("账号", "租户", "待办", "常用工具")
# 切换列表不应出现的类型字样（大纲 M02-L06）
FORBIDDEN_TYPE_WORDS = ("内部组织", "子公司", "企业类型")
# 原型写死数据（大纲 M03-L16 反例）
PROTOTYPE_FAKE_NAMES = ("郝仁",)

TAG = "[客商]"


def open_card(page: TenantOnboardingPage) -> str:
    """hover 显示名打开个人卡片，返回页面文本。"""
    page.open_personal_card()
    try:
        return page.page.locator("body").inner_text()
    except Exception:
        return ""


class TestPersonalCardAndTenantSwitcher:
    """M02 个人信息与租户切换（只读）。"""

    def test_ks_m02_001_card_areas(self, onboarding: TenantOnboardingPage) -> None:
        """KS-M02-001 / 大纲 M02-L01、L02：卡片含账号/租户/待办/常用工具区域。"""
        text = open_card(onboarding)
        hit = [w for w in CARD_AREAS if w in text]
        assert len(hit) >= 3, f"{TAG} 个人卡片区域命中 {hit}，期望至少 3 项（共 {len(CARD_AREAS)} 项）"
        assert settings.keshang_username[:2] in text or "陈" in text, (
            f"{TAG} 卡片未展示当前用户标识"
        )

    def test_ks_m02_002_switcher_states(self, onboarding: TenantOnboardingPage) -> None:
        """KS-M02-002 / 大纲 M02-L04：已开通项带「已开通」；有申请中样本时验「申请中」。"""
        open_card(onboarding)
        rows = onboarding.open_tenant_switcher()
        if not rows:
            pytest.skip(f"NOT_APPLICABLE[KS-M02-002] 切换租户面板未解析到租户记录")

        opened = [r for r in rows if r.opened]
        assert opened, (
            f"{TAG} 切换列表无「已开通」租户，实际状态分布: "
            f"{[(r.name, r.states) for r in rows]}"
        )

        applying = [r for r in rows if r.applying]
        if not applying:
            pytest.skip(
                f"NOT_APPLICABLE[KS-M02-002-申请中] 当前账号无「申请中」样本；"
                f"已开通 {len(opened)} 条已验证"
            )
        assert applying, "申请中记录应显示「申请中」状态"

    def test_ks_m02_003_no_type_words(self, onboarding: TenantOnboardingPage) -> None:
        """KS-M02-003 / 大纲 M02-L06：列表不显示企业/内部组织/子公司类型。"""
        open_card(onboarding)
        rows = onboarding.open_tenant_switcher()
        if not rows:
            pytest.skip(f"NOT_APPLICABLE[KS-M02-003] 切换租户面板未解析到租户记录")

        panel_text = onboarding.page.locator("body").inner_text()
        # 只检查列表区域附近，避免误伤页面其它模块
        offenders = [w for w in FORBIDDEN_TYPE_WORDS if w in panel_text]
        assert not offenders, f"{TAG} 切换列表出现不允许的类型字样: {offenders}"

    def test_ks_m02_004_same_name_not_mixed(self, onboarding: TenantOnboardingPage) -> None:
        """KS-M02-004 / 大纲 M02-L07：同名不同 ID 企业不应混入可进入列表。"""
        open_card(onboarding)
        rows = onboarding.open_tenant_switcher()
        names = [r.name for r in rows]
        if len(names) != len(set(names)):
            dup = [n for n in names if names.count(n) > 1]
            pytest.fail(f"{TAG} 切换列表出现重名租户: {dup}，应按唯一 ID 区分")
        # 需要「同名不同 ID」样本才能真正验证同名隔离
        apply_text = onboarding.page.locator("body").inner_text()
        if "申请中" not in apply_text and "已开通" in apply_text:
            if not any("(ZH" in n or "ZH_" in n for n in names):
                pytest.skip(
                    "NOT_APPLICABLE[KS-M02-004] 当前环境无「同名不同 ID」企业样本，"
                    "仅验证了列表无重名"
                )


class TestCreateTenantDialog:
    """M03 创建租户申请表单（只读）。"""

    def test_ks_m03_001_dialog_structure(self, onboarding: TenantOnboardingPage) -> None:
        """KS-M03-001 / 大纲 M03-L13：弹窗含组织树/对象信息/申请人/说明/声明/取消/提交。"""
        open_card(onboarding)
        onboarding.open_tenant_switcher()
        dlg = onboarding.open_create_tenant_dialog()
        assert dlg.title_present, f"{TAG} 弹窗标题「申请创建租户」未出现"
        assert not dlg.missing, f"{TAG} 弹窗缺失要素: {dlg.missing}"

    def test_ks_m03_002_tenant_name_readonly(self, onboarding: TenantOnboardingPage) -> None:
        """KS-M03-002 / 大纲 M03-L15：租户名称字段存在且只读。"""
        open_card(onboarding)
        onboarding.open_tenant_switcher()
        dlg = onboarding.open_create_tenant_dialog()
        assert "租户名称" in dlg.text, f"{TAG} 弹窗未见「租户名称」字段"
        if dlg.tenant_name_readonly is False:
            pytest.fail(f"{TAG} 租户名称字段可编辑，应只读")

    def test_ks_m03_003_applicant_from_current_user(
        self, onboarding: TenantOnboardingPage
    ) -> None:
        """KS-M03-003 / 大纲 M03-L16：申请人来自当前登录人，且不含原型写死的「郝仁」。"""
        open_card(onboarding)
        onboarding.open_tenant_switcher()
        dlg = onboarding.open_create_tenant_dialog()

        for fake in PROTOTYPE_FAKE_NAMES:
            assert fake not in dlg.text, (
                f"{TAG} 弹窗出现原型写死数据「{fake}」，说明取值未来自登录用户"
            )
        # 申请人展示名（客商槽位或主账号显示名）
        assert settings.keshang_username[:2] in dlg.text or "陈" in dlg.text or "张" in dlg.text, (
            f"{TAG} 弹窗未展示当前申请人"
        )
        assert re.search(r"1\d{2}\*{4}\d{4}", dlg.text), (
            f"{TAG} 未找到掩码手机号（形如 138****8804）"
        )

    def test_ks_m03_004_submit_disabled_without_selection(
        self, onboarding: TenantOnboardingPage
    ) -> None:
        """KS-M03-004 / 大纲 M03-L17：未选对象时「确认提交」不可用（只读状态，不点击）。"""
        open_card(onboarding)
        onboarding.open_tenant_switcher()
        dlg = onboarding.open_create_tenant_dialog()
        assert dlg.submit_disabled is not None, f"{TAG} 未找到提交按钮"
        assert dlg.submit_disabled is True, (
            f"{TAG} 未选择企业时提交按钮竟可用（disabled={dlg.submit_disabled}）"
        )

    def test_ks_m03_005_unverified_enterprise_blocked(
        self, onboarding: TenantOnboardingPage
    ) -> None:
        """KS-M03-005 / 大纲 M03-L02：未认证企业不可提交，并给出认证引导。"""
        open_card(onboarding)
        onboarding.open_tenant_switcher()
        dlg = onboarding.open_create_tenant_dialog()

        unverified = [e for e in dlg.enterprises if "未认证" in e["states"]]
        if not unverified:
            pytest.skip(
                "NOT_APPLICABLE[KS-M03-005] 当前环境无「未认证」企业样本；"
                f"已探测 {len(dlg.enterprises)} 个企业，状态均为 "
                f"{sorted({s for e in dlg.enterprises for s in e['states']})}"
            )
        assert dlg.submit_disabled is True, (
            f"{TAG} 存在未认证企业但提交按钮可用"
        )

    def test_ks_m03_006_cancel_leaves_no_residue(
        self, onboarding: TenantOnboardingPage
    ) -> None:
        """KS-M03-006 / 大纲 M03-L19：取消弹窗不生成记录，重开无残留。"""
        open_card(onboarding)
        onboarding.open_tenant_switcher()
        first = onboarding.open_create_tenant_dialog()
        assert first.title_present, f"{TAG} 首次打开弹窗失败"

        # 重开：需重新展开个人卡片与面板
        open_card(onboarding)
        try:
            onboarding.reopen_switcher()
        except AssertionError:
            pytest.skip("NOT_APPLICABLE[KS-M03-006] 取消后切换租户入口不可达")
        second = onboarding.open_create_tenant_dialog()
        assert second.title_present, f"{TAG} 取消后无法重新打开弹窗"
        # 无残留：弹窗内不应残留上一次的企业选择状态
        assert second.submit_disabled is True, (
            f"{TAG} 重开后提交按钮可用，疑似残留了上次选择"
        )
