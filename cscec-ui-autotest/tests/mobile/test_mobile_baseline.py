"""M5-移动端基础冒烟上线测试用例。

用例：
- M5-01 移动端冒烟账号登录和核心入口打开
- M5-02 移动端消息或待办列表与详情可打开
"""

from __future__ import annotations

import pytest

from pages.mobile.mobile_home_page import MobileHomePage


@pytest.mark.mobile
@pytest.mark.smoke
@pytest.mark.readonly
@pytest.mark.regression
class TestMobileBaseline:
    """M5 移动端基础冒烟用例集。"""

    def test_m5_01_mobile_login_and_home_accessible(self, logged_in_mobile_page):
        """M5-01 移动端冒烟账号登录和核心入口打开。"""
        home = MobileHomePage(logged_in_mobile_page)
        home.open_home()
        home.verify_home_container()

    def test_m5_02_mobile_message_todo_list_accessible(self, logged_in_mobile_page):
        """M5-02 移动端消息或待办列表与详情可打开。"""
        home = MobileHomePage(logged_in_mobile_page)
        home.open_home()
        home.verify_todo_cards()
