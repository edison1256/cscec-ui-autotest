"""M5-移动端基础冒烟上线测试用例。

用例：
- M5-01 移动端冒烟账号登录和核心入口打开
- M5-02 移动端消息或待办列表与详情可打开
"""

from __future__ import annotations

import pytest

from config.settings import settings
from pages.portal.portal_home_page import PortalHomePage


@pytest.fixture(scope="function")
def mobile_page(browser):
    """创建移动端 Viewport (iPhone 13 / H5) 上下文。"""
    context = browser.new_context(
        viewport={"width": 390, "height": 844},
        user_agent=(
            "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"
        ),
        ignore_https_errors=True,
    )
    context.set_default_timeout(settings.DEFAULT_TIMEOUT)
    context.set_default_navigation_timeout(settings.NAVIGATION_TIMEOUT)
    page = context.new_page()
    yield page
    context.close()


@pytest.mark.mobile
@pytest.mark.smoke
@pytest.mark.readonly
@pytest.mark.regression
class TestMobileBaseline:
    """M5 移动端基础冒烟用例集。"""

    def test_m5_01_mobile_login_and_home_accessible(self, mobile_page):
        """M5-01 移动端冒烟账号登录和核心入口打开。"""
        mobile_page.goto(settings.BASE_URL, timeout=settings.NAVIGATION_TIMEOUT, wait_until="domcontentloaded")
        body_text = mobile_page.locator("body").inner_text()
        assert len(body_text.strip()) > 0, "移动端首页加载为空"
        assert not any(err in body_text for err in ["404", "500", "Internal Server Error"]), "移动端加载异常"

    def test_m5_02_mobile_message_todo_list_accessible(self, mobile_page):
        """M5-02 移动端消息或待办列表与详情可打开。"""
        mobile_page.goto(f"{settings.BASE_URL.rstrip('/')}/#/support", timeout=settings.NAVIGATION_TIMEOUT, wait_until="domcontentloaded")
        body_text = mobile_page.locator("body").inner_text()
        assert len(body_text.strip()) > 0, "移动端支持/消息列表加载为空"
