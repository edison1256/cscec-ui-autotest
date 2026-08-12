"""
多候选定位器降级策略

从现有巡检脚本中提取的核心模式：当页面结构可能变化时，
提供多个候选定位器，按顺序尝试直到找到可用的。
"""

import re
from typing import Optional

from playwright.sync_api import Locator, Page

from core.logger import get_logger

logger = get_logger("locator")


def _build_role_locator(page: Page, selector_value: str) -> Locator:
    """解析 `button[name='查询']` 这类 role 写法。"""
    match = re.fullmatch(
        r"(?P<role>[\w-]+)(?:\[\s*name\s*=\s*(?P<quote>['\"]?)(?P<name>.*?)?(?P=quote)\s*\])?",
        selector_value,
    )
    if not match:
        raise ValueError(f"无效的 role 选择器: {selector_value}")

    role = match.group("role")
    name = match.group("name")
    if name:
        return page.get_by_role(role, name=name)
    return page.get_by_role(role)


def find_first_visible(
    page: Page,
    candidates: list[tuple[str, str]],
    timeout: int = 5000,
    description: str = "",
) -> Optional[Locator]:
    """
    从候选定位器列表中找到第一个可见的元素

    Args:
        page: Playwright Page 对象
        candidates: 定位器列表，每个元素为 (选择器类型, 选择器值)
                    例如 [("role", "button[name='登录']"), ("css", "#loginBtn")]
        timeout: 每个候选的等待时间（毫秒）
        description: 操作描述，用于日志

    Returns:
        第一个可见的 Locator，若全部不可见则返回 None

    用法::

        loc = find_first_visible(
            page,
            [
                ("role", "button[name='查询']"),
                ("css", ".ant-btn-primary"),
                ("text", "查询"),
            ],
            description="查询按钮",
        )
        if loc:
            loc.click()
    """
    for selector_type, selector_value in candidates:
        try:
            if selector_type == "role":
                loc = _build_role_locator(page, selector_value)
            elif selector_type == "text":
                loc = page.get_by_text(selector_value, exact=False)
            elif selector_type == "label":
                loc = page.get_by_label(selector_value)
            elif selector_type == "placeholder":
                loc = page.get_by_placeholder(selector_value)
            elif selector_type == "testid":
                loc = page.get_by_test_id(selector_value)
            elif selector_type == "title":
                loc = page.get_by_title(selector_value)
            elif selector_type == "css":
                loc = page.locator(selector_value)
            else:
                logger.warning(f"未知的定位器类型: {selector_type}")
                continue

            loc.wait_for(state="visible", timeout=timeout)
            logger.debug(f"[定位成功] {description or '元素'} → {selector_type}={selector_value}")
            return loc

        except Exception:
            continue

    logger.warning(f"[定位失败] {description or '元素'}：所有候选定位器均不可见")
    return None
