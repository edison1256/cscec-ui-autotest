"""服务中心发起申请：个人工作台身份的前置校验提醒。

需求（2026-11-18，UAT 新增）：
  门户【服务中心】发起任何资源时，若订阅用户当前为【个人工作台】，
  点击「发起申请」需提醒【切换其他租户】。

实测要点（决定了用例怎么写）：
  - 资源卡片容器是 `div[class*='publishItem']`，class 带 hash 后缀会变，只能包含匹配
  - 卡片默认只显示右下角箭头 icon；「立即申请」在 DOM 里但 `display:none`，
    **必须先 hover 卡片**才会浮现成可见链接
  - `force=True` 强行点隐藏的「立即申请」不会触发任何业务逻辑（URL/页面/标签页全无变化），
    所以用例必须断言「按钮在 hover 后可见」，否则会把"点了个寂寞"当成"点了没提示"
"""

from __future__ import annotations

import pytest

from pages.portal.service_center_page import ServiceCenterPage

pytestmark = [
    pytest.mark.service_center,
    pytest.mark.portal,
    pytest.mark.readonly,
]


@pytest.fixture(scope="function")
def service_center(logged_in_page) -> ServiceCenterPage:
    return ServiceCenterPage(logged_in_page)


class TestPersonalWorkbenchApplyGuard:
    """个人工作台身份下的发起申请守卫。"""

    @pytest.mark.xfail(
        strict=False,
        reason=(
            "UAT 实测（2026-11-18）：个人工作台身份下对资源「itsm-云资源」点「立即申请」，"
            "点击前后 URL 相同、无弹窗、无新标签页 —— 未出现「切换其他租户」提醒。"
            "对照组 SC-ST-002（普通租户）通过，证明链路可用，故这是业务侧未生效，"
            "需确认：该需求是否已部署到 UAT / 是否所有资源都要提示。"
            "需求生效后本用例会自动 xpass，届时移除标记转为硬断言。"
        ),
    )
    def test_sc_st_001_prompt_switch_tenant_on_apply(
        self, service_center: ServiceCenterPage
    ) -> None:
        """SC-ST-001：个人工作台下点「发起申请」应提示「切换其他租户」。

        判定三层，任何一层不过都说明需求未达成：
          1. 能 hover 出「立即申请」并点到（否则是选择器/交互变了，不是业务结论）
          2. 点击后出现了某种提示（弹窗/Toast/提示条/跳转到提示页）
          3. 提示内容包含「切换其他租户」
        """
        service_center.switch_to_personal_workbench()
        org = service_center.current_org_name
        assert "个人工作台" in org, f"未能切换到个人工作台身份，当前 orgName={org}"

        service_center.open_service_center()
        title = service_center.first_card_title()

        prompt = service_center.start_apply_on_first_card()

        assert prompt.clicked, (
            f"未能点击到「立即申请」（资源「{title}」）。"
            "可能卡片选择器或 hover 交互已变更，需先修 Page Object，"
            "此时的失败不代表业务结论"
        )

        assert prompt.has_switch_tenant_hint, (
            f"个人工作台身份下，对资源「{title}」点「立即申请」后"
            f"未出现「切换其他租户」提醒。\n"
            f"  点击前 URL: {prompt.url_before}\n"
            f"  点击后 URL: {prompt.url_after}\n"
            f"  是否新开标签页: {prompt.tab_opened} {prompt.new_tab_url}\n"
            f"  捕获到的弹窗/提示: {list(prompt.dialog_texts)}\n"
            "需求要求：个人工作台发起申请时必须提醒切换其他租户"
        )
        print(
            f"\n[提示] 资源「{title}」-> {list(prompt.dialog_texts)[:2]}"
        )


class TestOtherTenantApplyAllowed:
    """对照组：非个人工作台身份，不应出现该提醒。"""

    def test_sc_st_002_no_prompt_after_switch_to_tenant(
        self, service_center: ServiceCenterPage
    ) -> None:
        """SC-ST-002：切到普通租户后发起申请，不应提示「切换其他租户」。

        用途：防止实现成"任何身份都提示"，那样虽然 001 会绿，但功能被挡死。
        若当前环境没有可切换的普通租户，用例记 NOT_APPLICABLE。
        """
        service_center.switch_to_personal_workbench()

        # 打开切换租户面板，找一个非「个人工作台」的普通租户
        info = service_center.login_info()
        name = str(info.get("userName") or "")
        assert name, "未读到登录显示名"
        loc = service_center.page.get_by_text(name, exact=True).first
        if not loc.count():
            pytest.skip("NOT_APPLICABLE[SC-ST-002] 未找到显示名入口")
        loc.hover()
        service_center.page.wait_for_timeout(2200)
        sw = service_center.page.get_by_text("切换租户", exact=True).last
        if not sw.count():
            pytest.skip("NOT_APPLICABLE[SC-ST-002] 未找到「切换租户」")
        sw.click()
        service_center.page.wait_for_timeout(2800)

        body = service_center.page.locator("body").inner_text()
        candidates = [
            line.strip()
            for line in body.splitlines()
            if line.strip().endswith(("租户", "空间"))
            and "个人工作台" not in line
            and "切换" not in line
            and "创建" not in line
        ]
        if not candidates:
            pytest.skip("NOT_APPLICABLE[SC-ST-002] 没有可切换的普通租户")

        picked = candidates[0]
        target = service_center.page.get_by_text(picked, exact=True).last
        if not target.count():
            pytest.skip(f"NOT_APPLICABLE[SC-ST-002] 租户「{picked}」不可点")
        target.click()
        service_center.page.wait_for_timeout(4500)

        org_after = service_center.current_org_name
        assert "个人工作台" not in org_after, (
            f"切换后仍是个人工作台（orgName={org_after}），无法做对照"
        )

        service_center.open_service_center()
        prompt = service_center.start_apply_on_first_card()
        if not prompt.clicked:
            pytest.skip("NOT_APPLICABLE[SC-ST-002] 未能点击到申请入口")

        assert not prompt.has_switch_tenant_hint, (
            f"普通租户「{org_after}」下发起申请也出现了「切换其他租户」提醒，"
            f"说明守卫条件写错了（应对当前租户类型做判断）。提示: {list(prompt.dialog_texts)}"
        )
