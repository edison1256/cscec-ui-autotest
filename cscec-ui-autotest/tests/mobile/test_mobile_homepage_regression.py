"""中建云移动端首页 (#/homePage/customize1) 生产上线走查自动化回归用例。

包含用例：
- M-P0-HOME-001: 移动端首页加载与核心容器渲染
- M-P0-HOME-002: 移动端首页搜索栏展示与只读交互
- M-P0-HOME-003: 金刚区快捷应用图标网格展示
- M-P0-HOME-004: 轮播 Banner / 运营通知公告展示
- M-P0-HOME-005: 待办中心 / 任务统计卡片展示
- M-P0-HOME-006: 精选推荐资源/服务列表展示
- M-P0-NAV-001: 底部导航栏 (TabBar) 完整性与 Tab 切换
- M-P0-MINE-001: 个人中心（我的）页面展示与用户信息
- M-P0-RESP-001: 移动端多视口响应式兼容性校验
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser

from config.settings import settings
from pages.mobile.mobile_home_page import MobileHomePage


@pytest.mark.mobile
@pytest.mark.smoke
@pytest.mark.readonly
@pytest.mark.regression
class TestMobileHomepageRegression:
    """移动端首页生产上线走查用例集。"""

    def test_m_p0_home_001_container_rendering(self, logged_in_mobile_page):
        """M-P0-HOME-001: 移动端首页加载与核心容器渲染。"""
        home = MobileHomePage(logged_in_mobile_page)
        home.open_home()
        home.verify_home_container()

    def test_m_p0_home_002_search_bar_interaction(self, logged_in_mobile_page):
        """M-P0-HOME-002: 移动端首页搜索栏展示与只读交互。"""
        home = MobileHomePage(logged_in_mobile_page)
        home.open_home()
        home.verify_search_bar("云产品")

    def test_m_p0_home_003_icon_grid_visible(self, logged_in_mobile_page):
        """M-P0-HOME-003: 金刚区快捷应用图标网格展示。"""
        home = MobileHomePage(logged_in_mobile_page)
        home.open_home()
        home.verify_icon_grid()

    def test_m_p0_home_004_banner_announcement_visible(self, logged_in_mobile_page):
        """M-P0-HOME-004: 轮播 Banner / 运营通知公告展示。"""
        home = MobileHomePage(logged_in_mobile_page)
        home.open_home()
        home.verify_banner()

    def test_m_p0_home_005_todo_task_cards_visible(self, logged_in_mobile_page):
        """M-P0-HOME-005: 待办中心 / 任务统计卡片展示。"""
        home = MobileHomePage(logged_in_mobile_page)
        home.open_home()
        home.verify_todo_cards()

    def test_m_p0_home_006_recommended_resources_visible(self, logged_in_mobile_page):
        """M-P0-HOME-006: 精选推荐资源/服务列表展示。"""
        home = MobileHomePage(logged_in_mobile_page)
        home.open_home()
        home.verify_resource_cards()

    def test_m_p0_nav_001_bottom_tabbar_switch(self, logged_in_mobile_page):
        """M-P0-NAV-001: 底部导航栏 (TabBar) 完整性与 Tab 切换。"""
        home = MobileHomePage(logged_in_mobile_page)
        home.open_home()
        for tab_name in ["首页", "服务", "待办", "我的"]:
            home.switch_tab(tab_name)

    def test_m_p0_mine_001_profile_page_accessible(self, logged_in_mobile_page):
        """M-P0-MINE-001: 个人中心（我的）页面展示与用户信息。"""
        home = MobileHomePage(logged_in_mobile_page)
        home.open_home()
        home.verify_mine_page()

    @pytest.mark.parametrize(
        "viewport_spec",
        [
            pytest.param({"width": 390, "height": 844}, id="iPhone-13"),
            pytest.param({"width": 360, "height": 800}, id="Android-Standard"),
            pytest.param({"width": 428, "height": 926}, id="iPhone-Pro-Max"),
        ],
    )
    def test_m_p0_resp_001_multi_viewport_compatibility(self, browser: Browser, viewport_spec: dict):
        """M-P0-RESP-001: 移动端多视口响应式兼容性校验。"""
        auth_file = settings.auth_state_file
        storage_state = str(auth_file) if auth_file.exists() else None

        context = browser.new_context(
            viewport=viewport_spec,
            is_mobile=True,
            has_touch=True,
            ignore_https_errors=True,
            storage_state=storage_state,
        )
        page = context.new_page()
        try:
            home = MobileHomePage(page)
            home.open_home()
            home.verify_home_container()
        finally:
            context.close()
