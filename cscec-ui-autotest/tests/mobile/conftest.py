"""移动端模块专用 Fixture 配置。"""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from playwright.sync_api import Browser, BrowserContext, Page

from config.settings import settings


@pytest.fixture(scope="function")
def mobile_context(browser: Browser, auth_state_path: Path) -> BrowserContext:
    """创建移动端仿真浏览器上下文（带登录态）。

    登录态来自统一 fixture `auth_state_path`，因此 `--refresh-auth` 对移动端
    同样生效。此前直接读 `settings.auth_state_file`，导致刷新被跳过、
    且可能拿到只含控制台域的旧登录态 —— 移动端页面会停在 IDaaS 登录页。
    """
    storage_state = str(auth_state_path) if auth_state_path.exists() else None

    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        ),
        is_mobile=True,
        has_touch=True,
        ignore_https_errors=True,
        storage_state=storage_state,
    )
    context.set_default_timeout(settings.DEFAULT_TIMEOUT)
    context.set_default_navigation_timeout(settings.NAVIGATION_TIMEOUT)
    yield context
    context.close()


@pytest.fixture(scope="function")
def logged_in_mobile_page(mobile_context: BrowserContext) -> Page:
    """提供已登录的移动端 Page 实例。"""
    page = mobile_context.new_page()
    yield page
    page.close()
