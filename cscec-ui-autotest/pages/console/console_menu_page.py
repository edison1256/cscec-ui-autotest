"""Strict console menu-tree checks backed by the current menu API response."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from playwright.sync_api import Response, expect

from config.settings import settings
from core.execution_contract import PrerequisiteResult
from core.interaction_evidence import click_and_expect, require_actionable
from core.logger import get_logger
from pages.console.console_global_navigation_page import ConsoleGlobalNavigationPage


logger = get_logger("console_menu_page")


@dataclass(frozen=True)
class ConsoleMenuNode:
    """One authorized node returned by the console menu-tree endpoint."""

    title: str
    menu_code: str
    children: tuple["ConsoleMenuNode", ...]
    disabled: bool
    forbidden: bool

    @property
    def available(self) -> bool:
        """Return whether the backend exposes the node as usable."""
        return not self.disabled and not self.forbidden

    def child(self, title: str) -> "ConsoleMenuNode | None":
        """Return one exact direct child."""
        return next((node for node in self.children if node.title == title), None)


@dataclass(frozen=True)
class ConsoleMenuSnapshot:
    """Authorized top-level console menu tree captured during page startup."""

    nodes: tuple[ConsoleMenuNode, ...]

    @property
    def top_level_titles(self) -> tuple[str, ...]:
        """Return all non-empty top-level titles in API order."""
        return tuple(node.title for node in self.nodes if node.title)

    def top_level(self, title: str) -> ConsoleMenuNode | None:
        """Return one exact top-level menu node."""
        return next((node for node in self.nodes if node.title == title), None)

    def path(self, *titles: str) -> tuple[ConsoleMenuNode, ...] | None:
        """Resolve an exact menu path at any supported nesting depth."""
        if not titles:
            return None
        current = self.top_level(titles[0])
        if current is None:
            return None
        resolved = [current]
        for title in titles[1:]:
            current = current.child(title)
            if current is None:
                return None
            resolved.append(current)
        return tuple(resolved)


class ConsoleMenuPage(ConsoleGlobalNavigationPage):
    """Exercise the effective left menu that the backend grants to this account."""

    MENU_API_PATTERN = re.compile(
        r"/engine/metadata/getMenuTreeForPortal\?moduleCode="
    )

    def __init__(self, page) -> None:
        super().__init__(page)
        self._menu_snapshot: ConsoleMenuSnapshot | None = None

    def open_console_home(self) -> "ConsoleMenuPage":
        """Open the console and capture the menu authorization response."""
        with self.page.expect_response(
            lambda response: bool(self.MENU_API_PATTERN.search(response.url)),
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as response_info:
            super().open_console_home()

        self._menu_snapshot = self._parse_menu_response(response_info.value)
        assert self._menu_snapshot.nodes, "控制台菜单接口成功但未返回任何顶层菜单"
        logger.info(
            "[前置条件] 控制台菜单接口返回 %s 个顶层节点",
            len(self._menu_snapshot.nodes),
        )
        return self

    def menu_tree_prerequisite(self) -> PrerequisiteResult:
        """Describe whether the account received a usable menu tree."""
        snapshot = self._require_snapshot()
        available = tuple(node.title for node in snapshot.nodes if node.available)
        return PrerequisiteResult(
            satisfied=bool(available),
            reason="当前账号未获授权任何可用控制台菜单",
            expected="至少一个可用顶层菜单",
            actual=", ".join(available) or "<empty>",
        )

    def top_level_menu_prerequisite(self, title: str) -> PrerequisiteResult:
        """Describe whether one target menu was granted before clicking it."""
        snapshot = self._require_snapshot()
        node = snapshot.top_level(title)
        satisfied = node is not None and node.available
        if node is None:
            actual = ", ".join(snapshot.top_level_titles) or "<empty>"
            reason = f"菜单接口未向当前账号下发顶层菜单“{title}”"
        else:
            actual = (
                f"disabled={node.disabled}, forbidden={node.forbidden}, "
                f"children={len(node.children)}"
            )
            reason = f"菜单接口将顶层菜单“{title}”标记为不可用"
        return PrerequisiteResult(
            satisfied=satisfied,
            reason=reason,
            expected=f"顶层菜单“{title}”已授权且可用",
            actual=actual,
        )

    def child_menu_prerequisite(
        self,
        parent_title: str,
        child_title: str,
    ) -> PrerequisiteResult:
        """Describe whether an exact child menu was granted before opening it."""
        parent = self._require_snapshot().top_level(parent_title)
        child = next(
            (
                candidate
                for candidate in parent.children
                if candidate.title == child_title
            ),
            None,
        ) if parent is not None else None
        satisfied = (
            parent is not None
            and parent.available
            and child is not None
            and child.available
        )
        available_children = (
            tuple(candidate.title for candidate in parent.children if candidate.available)
            if parent is not None
            else ()
        )
        return PrerequisiteResult(
            satisfied=satisfied,
            reason=f"菜单接口未下发可用路径“{parent_title} -> {child_title}”",
            expected=f"直属菜单“{child_title}”已授权且可用",
            actual=", ".join(available_children) or "<empty>",
        )

    def menu_path_prerequisite(self, *titles: str) -> PrerequisiteResult:
        """Describe whether every node in an exact nested menu path is usable."""
        resolved = self._require_snapshot().path(*titles)
        satisfied = resolved is not None and all(node.available for node in resolved)
        actual = (
            " -> ".join(node.title for node in resolved)
            if resolved is not None
            else "<missing>"
        )
        path_text = " -> ".join(titles)
        return PrerequisiteResult(
            satisfied=satisfied,
            reason=f"菜单接口未下发完整可用路径“{path_text}”",
            expected=f"菜单路径“{path_text}”全部已授权且可用",
            actual=actual,
        )

    def open_menu_path(
        self,
        *titles: str,
        response_pattern: str,
        route_pattern: str,
    ) -> Response:
        """Expand an authorized path and open its leaf while capturing its API."""
        resolved = self._require_snapshot().path(*titles)
        assert resolved is not None and all(node.available for node in resolved), (
            f"菜单路径未通过执行前置条件: {' -> '.join(titles)}"
        )
        for node in resolved[:-1]:
            item = self._menu_item(node.title)
            require_actionable(item, f"展开控制台菜单组 {node.title}")
            if item.get_attribute("aria-expanded") != "true":
                click_and_expect(
                    item,
                    lambda item=item: expect(item).to_have_attribute(
                        "aria-expanded", "true"
                    ),
                    action_name=f"展开控制台菜单组 {node.title}",
                )

        leaf = self._menu_item(resolved[-1].title)
        with self.page.expect_response(
            lambda response: response_pattern in response.url,
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as response_info:
            click_and_expect(
                leaf,
                lambda: expect(self.page).to_have_url(
                    re.compile(route_pattern), timeout=settings.NAVIGATION_TIMEOUT
                ),
                action_name=f"打开控制台菜单 {' -> '.join(titles)}",
            )
        self.assertions.page_not_blank_or_error()
        return response_info.value

    def open_menu_route(
        self,
        *titles: str,
        route_pattern: str,
    ) -> "ConsoleMenuPage":
        """Open an authorized leaf when the page exposes no stable business API."""
        resolved = self._require_snapshot().path(*titles)
        assert resolved is not None and all(node.available for node in resolved), (
            f"菜单路径未通过执行前置条件: {' -> '.join(titles)}"
        )
        for node in resolved[:-1]:
            item = self._menu_item(node.title)
            require_actionable(item, f"展开控制台菜单组 {node.title}")
            if item.get_attribute("aria-expanded") != "true":
                click_and_expect(
                    item,
                    lambda item=item: expect(item).to_have_attribute(
                        "aria-expanded", "true"
                    ),
                    action_name=f"展开控制台菜单组 {node.title}",
                )

        leaf = self._menu_item(resolved[-1].title)
        require_actionable(leaf, f"打开控制台菜单 {' -> '.join(titles)}")
        click_and_expect(
            leaf,
            lambda: expect(self.page).to_have_url(
                re.compile(route_pattern), timeout=settings.NAVIGATION_TIMEOUT
            ),
            action_name=f"打开控制台菜单 {' -> '.join(titles)}",
        )
        self.assertions.page_not_blank_or_error()
        logger.info("[导航] 控制台左侧菜单 -> %s", " -> ".join(titles))
        return self

    def verify_menu_tree_rendered(self) -> "ConsoleMenuPage":
        """Require every available API top-level node to render in the sidebar."""
        snapshot = self._require_snapshot()
        for node in snapshot.nodes:
            if node.available:
                expect(self.page.get_by_text(node.title, exact=True).first).to_be_visible()
        logger.info("[断言] 菜单接口顶层节点均已渲染到左侧菜单")
        return self

    def expand_menu_group(self, title: str) -> "ConsoleMenuPage":
        """Expand an authorized group and require all direct API children."""
        node = self._require_snapshot().top_level(title)
        assert node is not None and node.available, f"菜单“{title}”未通过执行前置条件"
        assert node.children, f"菜单接口中的“{title}”不是可展开菜单组"

        title_text = self.page.get_by_text(title, exact=True).first
        menu_item = title_text.locator("xpath=ancestor::*[@role='menuitem'][1]")
        require_actionable(menu_item, f"展开控制台菜单组 {title}")
        if menu_item.get_attribute("aria-expanded") != "true":
            click_and_expect(
                menu_item,
                lambda: expect(menu_item).to_have_attribute("aria-expanded", "true"),
                action_name=f"展开控制台菜单组 {title}",
            )

        submenu = menu_item.locator("xpath=..").locator("ul[role='menu']").first
        expect(submenu).to_be_visible()
        for child in node.children:
            if child.available:
                expect(submenu.get_by_text(child.title, exact=True).first).to_be_visible()
        logger.info(
            "[断言] 菜单组 %s 展开并渲染 %s 个直属子项",
            title,
            len(tuple(child for child in node.children if child.available)),
        )
        return self

    def open_flow_page(self) -> "ConsoleMenuPage":
        """Open the authorized standalone flow entry and prove its route."""
        flow_text = self.page.get_by_text("流程", exact=True).first
        menu_item = flow_text.locator("xpath=ancestor::*[@role='menuitem'][1]")

        click_and_expect(
            menu_item,
            lambda: expect(self.page).to_have_url(
                re.compile(r"[#/]flowmodel(?:[/?]|$)"),
                timeout=settings.NAVIGATION_TIMEOUT,
            ),
            action_name="打开控制台流程入口",
        )
        self.assertions.page_not_blank_or_error()
        logger.info("[导航] 控制台左侧菜单 -> 流程")
        return self

    def _require_snapshot(self) -> ConsoleMenuSnapshot:
        assert self._menu_snapshot is not None, "尚未捕获控制台菜单接口响应"
        return self._menu_snapshot

    def _menu_item(self, title: str):
        """Locate the visible menu item that owns an exact title."""
        title_text = self.page.get_by_text(title, exact=True).first
        return title_text.locator("xpath=ancestor::*[@role='menuitem'][1]")

    @classmethod
    def _parse_menu_response(cls, response: Response) -> ConsoleMenuSnapshot:
        assert response.status == 200, (
            f"控制台菜单接口 HTTP 状态异常: {response.status} {response.url}"
        )
        payload = response.json()
        assert isinstance(payload, dict), "控制台菜单接口响应不是 JSON 对象"
        code = payload.get("code")
        assert type(code) is int and code == 0, (
            f"控制台菜单接口业务失败: code={code!r}, "
            f"message={payload.get('message')!r}"
        )
        data = payload.get("data")
        assert isinstance(data, list), "控制台菜单接口 data 不是列表"
        return ConsoleMenuSnapshot(
            tuple(cls._parse_menu_node(raw) for raw in data if isinstance(raw, dict))
        )

    @classmethod
    def _parse_menu_node(cls, raw: dict[str, Any]) -> ConsoleMenuNode:
        children = raw.get("children")
        child_rows = children if isinstance(children, list) else []
        return ConsoleMenuNode(
            title=str(raw.get("title") or "").strip(),
            menu_code=str(raw.get("menuCode") or raw.get("key") or ""),
            children=tuple(
                cls._parse_menu_node(child)
                for child in child_rows
                if isinstance(child, dict)
            ),
            disabled=raw.get("disabled") is True,
            forbidden=raw.get("forbid") is True,
        )
