"""门户「服务中心」Page Object。

2026-11-18 实测要点（UAT，cloud-uat.cscec.com）：
  - 服务中心路由 `#/service-center/2`，页面标题「云产品」
  - 资源卡片容器 `div[class*='publishItem']`（实测 240×284，class 带 hash 后缀）
  - 卡片默认只显示右下角箭头 icon；**hover 后**才在左下角浮现「立即申请」文字链接
  - 「立即申请」在 DOM 里一直存在但 `display:none`，`force=True` 点它不会触发业务逻辑
    （实测 URL/页面/标签页全无变化），必须先 hover

身份要求：本模块的所有用例都要求当前登录身份为「个人工作台」
（`orgName=个人工作台`，`orgNo=ZH_01_0000_0000_000X`）。若当前不是，
用 `switch_to_personal_workbench()` 走「显示名 → 切换租户」切过去。
"""

from __future__ import annotations

from dataclasses import dataclass

from config.settings import settings
from core.base_page import BasePage


@dataclass(frozen=True)
class ApplyPrompt:
    """点「立即申请」之后的现场。"""

    clicked: bool
    url_before: str
    url_after: str
    dialog_texts: tuple[str, ...]
    tab_opened: bool
    new_tab_url: str = ""
    specs_seen: tuple[str, ...] = ()
    spec_clicked: str = ""

    @property
    def navigated(self) -> bool:
        return self.url_after != self.url_before or self.tab_opened

    @property
    def has_switch_tenant_hint(self) -> bool:
        blob = " ".join(self.dialog_texts) + " " + self.new_tab_url
        # UAT 实测文案（Ant Modal）：
        #   注意 / 切换到非个人工作台租户，开启便捷采购。 / 取消 / 切换租户
        return any(w in blob for w in ("非个人工作台租户", "切换租户", "切换其他租户"))


class ServiceCenterPage(BasePage):
    """服务中心（门户，只读 + 只点申请入口，不提交表单）。"""

    PAGE_NAME = "服务中心"
    CARD_SELECTOR = "div[class*='publishItem']"

    def ensure_portal(self) -> "ServiceCenterPage":
        """确保停在门户（cloud 域）且已登录。

        `logged_in_page` 可能停在 irp（控制台）域 —— 那里和 cloud 不同源，
        `__login_info__` 读不到，切换租户面板也不存在。
        只导航到门户**根域名**（等价于用户输入网址），不含任何功能页路由。
        """
        page = self.page
        if "cloud" not in (page.url or "").lower():
            page.goto(
                settings.PORTAL_BASE_URL,
                wait_until="domcontentloaded",
                timeout=settings.NAVIGATION_TIMEOUT,
            )
            page.wait_for_timeout(4000)
            for _ in range(2):
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)

        # 若门户尚未登录（跳到了 SSO），走一次正常登录
        if not self.login_info().get("userName"):
            from pages.portal.login_page import LoginPage

            LoginPage(page).login_portal()
            page.wait_for_timeout(3000)
            for _ in range(2):
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
        return self

    def login_info(self) -> dict:
        try:
            v = self.page.evaluate(
                "() => { const s = localStorage.getItem('__login_info__');"
                " return s ? JSON.parse(s) : null; }"
            )
        except Exception:
            return {}
        return v if isinstance(v, dict) else {}

    @property
    def current_org_name(self) -> str:
        return str(self.login_info().get("orgName") or "")

    def is_personal_workbench(self) -> bool:
        return "个人工作台" in self.current_org_name

    def switch_to_personal_workbench(self) -> "ServiceCenterPage":
        """门户 → 右上角显示名 → 切换租户 → 个人工作台。

        已在该身份时直接返回（幂等）。
        """
        self.ensure_portal()
        if self.is_personal_workbench():
            return self

        name = str(self.login_info().get("userName") or "")
        assert name, "未读到登录显示名（__login_info__.userName）"
        loc = self.page.get_by_text(name, exact=True).first
        assert loc.count(), f"未找到显示名「{name}」"
        loc.hover()
        self.page.wait_for_timeout(2200)

        sw = self.page.get_by_text("切换租户", exact=True).last
        assert sw.count(), "个人卡片中未找到「切换租户」"
        sw.click()
        self.page.wait_for_timeout(2800)

        target = self.page.get_by_text("个人工作台", exact=True)
        assert target.count(), "切换租户面板中未找到「个人工作台」"
        target.last.click()
        self.page.wait_for_timeout(4500)
        for _ in range(2):
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(300)
        return self

    def open_service_center(self) -> "ServiceCenterPage":
        """点导航「服务中心」。"""
        self.ensure_portal()
        for factory in (
            lambda: self.page.get_by_role("link", name="服务中心", exact=True).last,
            lambda: self.page.get_by_text("服务中心", exact=True).last,
        ):
            try:
                loc = factory()
                if loc.count() and loc.is_visible(timeout=2500):
                    loc.click()
                    self.page.wait_for_timeout(4500)
                    break
            except Exception:
                continue
        assert self.cards.count() > 0, (
            f"服务中心未渲染资源卡片（selector={self.CARD_SELECTOR}），"
            f"当前 URL={self.page.url[:120]}"
        )
        return self

    @property
    def cards(self):
        return self.page.locator(self.CARD_SELECTOR)

    def first_card_title(self) -> str:
        try:
            return (self.cards.first.inner_text() or "").splitlines()[0][:60]
        except Exception:
            return ""

    # popover 规格项文案（UAT 实测，云资源类资源）
    SPEC_KEYWORD_HINT = ("申请", "订阅")

    def start_apply_on_first_card(self, spec_keyword: str | None = None) -> ApplyPrompt:
        """hover 卡片 → 点「立即申请」→ 点规格项 → 进订阅页，返回现场。

        用户 2026-11-18 纠正的交互链（此前只做到第一步就下了结论）：
          1. hover 卡片才出现「立即申请」
          2. 点它 → 弹出 Ant popover，列出可用规格
               实测文案：云资源变更 / 云资源回收 / **云资源申请**
          3. 点规格 → 进入订阅页
          4. 「切换其他租户」提示出现在**第 3 步之后**

        不填表、不提交；只观察提示。
        """
        cards = self.cards
        assert cards.count() > 0, "服务中心没有可用的资源卡片"

        card = cards.first
        card.hover(timeout=8000)
        self.page.wait_for_timeout(1200)

        btn = card.get_by_text("立即申请", exact=True)
        if not (btn.count() > 0 and btn.first.is_visible()):
            return ApplyPrompt(
                clicked=False,
                url_before=self.page.url,
                url_after=self.page.url,
                dialog_texts=(),
                tab_opened=False,
                specs_seen=(),
            )

        # 第 2 步：点「立即申请」，弹出规格 popover
        url_before = self.page.url
        btn.first.click(timeout=8000)
        self.page.wait_for_timeout(2500)

        popover = self.page.locator(".ant-popover-inner-content").last
        specs: tuple[str, ...] = ()
        if popover.count():
            try:
                raw = popover.inner_text() or ""
                specs = tuple(x.strip() for x in raw.splitlines() if x.strip())
            except Exception:
                specs = ()

        keywords = (spec_keyword,) if spec_keyword else self.SPEC_KEYWORD_HINT
        chosen = None
        for kw in keywords:
            for name in specs:
                if kw in name:
                    target = popover.get_by_text(name, exact=True).first
                    if target.count():
                        chosen = name
                        break
            if chosen:
                break
        if chosen is None and specs:
            chosen = specs[0]

        if chosen is None:
            return ApplyPrompt(
                clicked=True,
                url_before=url_before,
                url_after=self.page.url,
                dialog_texts=(),
                tab_opened=False,
                specs_seen=specs,
            )

        # 第 3 步：点规格，进订阅页
        ctx = self.page.context
        pages_before = len(ctx.pages)
        try:
            popover.get_by_text(chosen, exact=True).first.click(timeout=8000)
        except Exception as exc:  # noqa: BLE001
            return ApplyPrompt(
                clicked=True,
                url_before=url_before,
                url_after=self.page.url,
                dialog_texts=(f"点击规格「{chosen}」失败: {type(exc).__name__}",),
                tab_opened=False,
                specs_seen=specs,
            )
        self.page.wait_for_timeout(4500)

        tab_opened = len(ctx.pages) > pages_before
        target = ctx.pages[-1] if tab_opened else self.page
        if tab_opened:
            try:
                target.wait_for_load_state("domcontentloaded", timeout=15000)
            except Exception:
                pass
            target.wait_for_timeout(2000)

        dialogs: list[str] = []
        for sel in (
            ".ant-modal-content",
            ".ant-message-notice-content",
            "[role='dialog']",
            ".ant-notification-notice",
            ".ant-alert",
            ".ant-result-title",
            ".ant-result-subtitle",
        ):
            try:
                loc = target.locator(sel)
                for i in range(min(loc.count(), 4)):
                    el = loc.nth(i)
                    if el.is_visible():
                        text = (el.inner_text() or "").strip()
                        if text:
                            dialogs.append(text[:400])
            except Exception:
                continue

        return ApplyPrompt(
            clicked=True,
            url_before=url_before,
            url_after=target.url,
            dialog_texts=tuple(dialogs),
            tab_opened=tab_opened,
            new_tab_url=target.url if tab_opened else "",
            specs_seen=specs,
            spec_clicked=chosen,
        )
