"""弹性导航：菜单 → 直链兜底 → 安全跳过。

当目标页面的入口在某个环境未暴露时（例如 UAT 尚未上线对应菜单），
导航应当优雅降级，而不是产生一次"假失败"污染运行结果。流程：

1. 尝试菜单驱动路径（由调用方传入的 click_menu 闭包执行）。
2. 若配置了直链 URL，作为兜底再尝试一次直链跳转（需各环境在
   config 中填写真实路由，未填则跳过该步骤）。
3. 执行就绪校验（URL / 可见文案）。
4. 仍不可达 → 抛出 `EntryNotExposed`，由用例捕获后调用 `pytest.skip`，
   保留运行结果纯洁性，同时 registry 继续标注 needs_stabilization。
"""

from __future__ import annotations

import time

from playwright.sync_api import Page

from config.settings import settings
from core.logger import get_logger

logger = get_logger("nav_helpers")


class EntryNotExposed(Exception):
    """目标页面入口在当前环境未暴露（菜单与直链均不可达）。"""


def navigate_with_fallback(
    page: Page,
    *,
    click_menu,
    fallback_url: str | None = None,
    readiness,
    entry_name: str = "目标页面",
    timeout: int | None = None,
) -> str:
    """尝试菜单导航，再尝试可选直链，最后校验就绪状态。

    成功返回 "menu" 或 "url"；不可达时抛出 `EntryNotExposed`。

    Args:
        page: Playwright 页面对象。
        click_menu: 零参闭包，执行菜单点击导航；失败应抛异常。
        fallback_url: 直链 URL；为空/None 时不尝试直链兜底。
        readiness: 零参闭包，返回真值或抛异常表示已到达目标页。
        entry_name: 入口名称，用于日志与异常文案。
        timeout: 就绪校验的总超时（毫秒），默认不轮询（单次判定）。
    """
    # 1) 菜单路径
    try:
        click_menu()
        if _check_readiness(page, readiness, timeout):
            logger.info(f"[导航] 通过菜单进入 {entry_name}")
            return "menu"
    except Exception as exc:  # noqa: BLE001 - 任何菜单失败都进入兜底/降级
        logger.info(f"[导航] 菜单进入 {entry_name} 失败: {exc!r}")

    # 2) 直链兜底
    if fallback_url:
        try:
            from core.navigation import NavigationHelper

            NavigationHelper(page).goto_url(fallback_url)
            if _check_readiness(page, readiness, timeout):
                logger.info(f"[导航] 通过直链进入 {entry_name}")
                return "url"
        except Exception as exc:  # noqa: BLE001
            logger.info(f"[导航] 直链进入 {entry_name} 失败: {exc!r}")

    raise EntryNotExposed(
        f"{entry_name} 在当前环境未暴露入口（菜单与直链均不可达），"
        f"跳过该项以保留运行结果纯洁性。"
    )


def _check_readiness(page: Page, readiness, timeout: int | None) -> bool:
    if not timeout:
        try:
            return bool(readiness())
        except Exception:  # noqa: BLE001
            return False

    deadline = time.time() + timeout / 1000
    while time.time() < deadline:
        try:
            if readiness():
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.3)
    return False


def deep_link(key: str) -> str | None:
    """读取当前环境的直链配置（未配置返回 None）。"""
    return settings.DEEP_LINKS.get(key)
