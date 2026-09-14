"""Web-first interaction checkpoints for production UI workflows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from playwright.sync_api import Locator, Page, expect


@dataclass(frozen=True)
class SurfaceSnapshot:
    """Observable page state before or after a user interaction."""

    url: str
    active_tabs: tuple[str, ...]
    visible_overlays: int


def capture_surface(page: Page) -> SurfaceSnapshot:
    """Capture stable state that can prove an interaction changed the UI."""
    active_tabs = tuple(
        text.strip()
        for text in page.locator('[role="tab"][aria-selected="true"]').all_inner_texts()
        if text.strip()
    )
    overlays = page.locator(
        ".ant-modal:visible, .ant-drawer:visible, .el-dialog:visible, .el-drawer:visible"
    ).count()
    return SurfaceSnapshot(page.url, active_tabs, overlays)


def require_actionable(locator: Locator, action_name: str) -> Locator:
    """Require the exact target to be visible and enabled before interaction."""
    expect(locator, f"{action_name}: 目标元素不可见").to_be_visible()
    expect(locator, f"{action_name}: 目标元素不可用").to_be_enabled()
    return locator


def click_and_expect(
    locator: Locator,
    expectation: Callable[[], None],
    *,
    action_name: str,
) -> tuple[SurfaceSnapshot, SurfaceSnapshot]:
    """Click an actionable element and require a caller-owned Web-First result."""
    page = locator.page
    before = capture_surface(page)
    require_actionable(locator, action_name).click()
    try:
        expectation()
    except Exception as exc:
        raise AssertionError(
            f"{action_name}: 点击后未达到预期状态; current_url={page.url}"
        ) from exc
    return before, capture_surface(page)


def require_surface_change(
    before: SurfaceSnapshot,
    after: SurfaceSnapshot,
    action_name: str,
) -> None:
    """Require URL, active Tab, or visible overlay state to change."""
    changed = (
        before.url != after.url
        or before.active_tabs != after.active_tabs
        or before.visible_overlays != after.visible_overlays
    )
    assert changed, (
        f"{action_name}: 点击后 URL、活动 Tab 和弹层状态均未变化; "
        f"url={after.url}"
    )


def require_business_identity(
    locator: Locator,
    expected: str,
    object_name: str,
) -> None:
    """Require a detail surface to identify the intended business object."""
    expect(locator, f"{object_name}: 唯一标识未显示").to_contain_text(expected)
