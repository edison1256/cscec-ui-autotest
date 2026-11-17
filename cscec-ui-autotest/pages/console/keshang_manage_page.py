"""控制台「权限管理 → 客商管理」Page Object（只读）。

菜单层级（2026-11-17 生产实测，用户截图确认）：
    权限管理 → 客商管理 → 认证审核 / 用户中心 / 企业名录 / 客商列表 /
                            入驻配置 / 企业类型管理 / 认证材料库

路由统一为 `#/sub/ecosystem/*`：
    certReview / userCenter / certifiedClientList / clientManage /
    onboardConfig / orgTypeManage / docVerify

导航边界：只直链到控制台根域名（用户 2026-11-17 明确允许），
进入后一律点左侧菜单树，不拼任何 `#/` 路由。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from config.settings import settings
from core.base_page import BasePage

# 子菜单 → 期望路由片段（用于确认点击真的跳到了对应页面）
SUBMENU_ROUTES: dict[str, str] = {
    "认证审核": "ecosystem/certReview",
    "用户中心": "ecosystem/userCenter",
    "企业名录": "ecosystem/certifiedClientList",
    "客商列表": "ecosystem/clientManage",
    "入驻配置": "ecosystem/onboardConfig",
    "企业类型管理": "ecosystem/orgTypeManage",
    "认证材料库": "ecosystem/docVerify",
}

# 每个子菜单页面上应出现的特征控件/文案（生产实测）
SUBMENU_MARKERS: dict[str, tuple[str, ...]] = {
    "认证审核": ("查询", "重置", "全部空间", "全部类型"),
    "用户中心": ("注册用户总数",),
    "企业名录": ("查询", "全部类型"),
    "客商列表": ("查询",),
    "入驻配置": ("选择空间",),
    "企业类型管理": ("企业类型",),
    "认证材料库": ("认证材料",),
}


@dataclass(frozen=True)
class SubMenuState:
    """打开某个子菜单后的现场状态。"""

    name: str
    url: str
    markers_hit: tuple[str, ...]
    body_head: str

    @property
    def route_ok(self) -> bool:
        expected = SUBMENU_ROUTES.get(self.name, "")
        return bool(expected) and expected in self.url

    @property
    def missing_markers(self) -> tuple[str, ...]:
        expected = SUBMENU_MARKERS.get(self.name, ())
        return tuple(m for m in expected if m not in self.markers_hit)


class KeshangManagePage(BasePage):
    """客商管理（控制台，只读）。"""

    PAGE_NAME = "客商管理"

    def open_console(self) -> "KeshangManagePage":
        """到控制台首页。

        只导航到 irp **根域名**（等价于用户输入网址），不含任何功能页路由。
        """
        page = self.page
        if "irp" not in (page.url or "").lower():
            page.goto(
                settings.CONSOLE_BASE_URL,
                wait_until="domcontentloaded",
                timeout=settings.NAVIGATION_TIMEOUT,
            )
            page.wait_for_timeout(4000)
            for _ in range(2):
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)
        return self

    def _click(self, label: str, wait: int = 2500) -> bool:
        for factory in (
            lambda: self.page.get_by_role("menuitem", name=label, exact=True).last,
            lambda: self.page.get_by_text(label, exact=True).last,
        ):
            try:
                loc = factory()
                if loc.count() and loc.is_visible(timeout=1800):
                    loc.click()
                    self.page.wait_for_timeout(wait)
                    return True
            except Exception:
                continue
        return False

    def expand_keshang_menu(self) -> "KeshangManagePage":
        """展开「权限管理 → 客商管理」。"""
        assert self._click("权限管理", 2200), "未找到「权限管理」一级菜单"
        assert self._click("客商管理", 2800), "未找到「客商管理」子菜单"
        return self

    def open_submenu(self, name: str) -> SubMenuState:
        """点开指定子菜单并返回现场状态。"""
        self.open_console()
        self.expand_keshang_menu()
        assert self._click(name, 5000), f"未找到客商管理子菜单「{name}」"
        self.page.wait_for_timeout(2000)
        try:
            body = self.page.locator("body").inner_text()
        except Exception:
            body = ""
        # Ant Design 中文按钮常带字间距（「查 询」「重 置」「取 消」），
        # 直接子串匹配会漏，先去掉所有空白再比。
        compact = re.sub(r"\s+", "", body)
        markers = tuple(
            w for w in SUBMENU_MARKERS.get(name, ()) if re.sub(r"\s+", "", w) in compact
        )
        return SubMenuState(
            name=name,
            url=self.page.url,
            markers_hit=markers,
            body_head=body[:800],
        )

    def visible_submenus(self) -> tuple[str, ...]:
        """展开后可见的子菜单清单（用于校验菜单完整性）。"""
        self.open_console()
        self.expand_keshang_menu()
        try:
            body = self.page.locator("body").inner_text()
        except Exception:
            body = ""
        return tuple(n for n in SUBMENU_ROUTES if n in body)
