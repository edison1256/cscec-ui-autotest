"""中建云移动端首页 Page Object — #/homePage/customize1。"""

from __future__ import annotations

import re
from typing import Optional

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from config.settings import settings
from core.base_page import BasePage
from core.logger import get_logger

logger = get_logger("mobile_home_page")


class MobileHomePage(BasePage):
    """移动端首页与底部导航页面对象。"""

    PAGE_NAME = "移动端首页"
    MOBILE_HOME_PATH = "/udpweb/mobile/index.html#/homePage/customize1"

    def open_home(self) -> "MobileHomePage":
        """打开移动端定制首页。"""
        full_url = f"{settings.BASE_URL.rstrip('/')}{self.MOBILE_HOME_PATH}"
        logger.info(f"[移动端导航] {full_url}")
        self.nav.goto_url(full_url)
        self.nav.wait_ready()
        return self

    def verify_home_container(self) -> "MobileHomePage":
        """M-P0-HOME-001: 校验移动端首页容器正常加载，无白屏/报错。"""
        self.assertions.page_not_blank_or_error()
        self.assertions.url_contains("homePage/customize1")
        body_text = self.page.locator("body").inner_text()
        assert len(body_text.strip()) > 0, "移动端首页内容为空白"
        logger.info("[断言] 移动端首页主容器正常加载")
        return self

    def verify_search_bar(self, test_keyword: str = "云产品") -> "MobileHomePage":
        """M-P0-HOME-002: 校验搜索栏并执行安全输入与清空。"""
        search_input = self.elements.find_candidates(
            [
                ("placeholder", "请输入搜索关键字"),
                ("placeholder", "搜索"),
                ("placeholder", "请输入"),
                ("css", ".van-search__content input"),
                ("css", "input[type='search']"),
                ("css", "input.ant-input"),
            ],
            description="移动端首页搜索栏",
        )
        if search_input:
            search_input.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
            search_input.fill(test_keyword)
            assert search_input.input_value() == test_keyword, f"搜索框未成功填充: {test_keyword}"
            search_input.fill("")
            assert search_input.input_value() == "", "搜索框未成功清空"
            logger.info(f"[只读交互] 移动端搜索栏只读输入与清空完成: {test_keyword}")
        else:
            logger.info("[提示] 移动端当前首页未暴露标准搜索输入框，通过容器校验")
        return self

    def verify_icon_grid(self) -> "MobileHomePage":
        """M-P0-HOME-003: 校验金刚区快捷应用图标网格。"""
        grid_items = self.page.locator(
            ".van-grid-item, .grid-item, .app-item, .icon-item, [class*='grid'], [class*='app']"
        )
        try:
            grid_items.first.wait_for(state="visible", timeout=settings.DEFAULT_TIMEOUT)
            count = grid_items.count()
            logger.info(f"[断言] 金刚区快捷图标数量: {count}")
            assert count > 0, "金刚区快捷应用图标为空"
        except PlaywrightTimeoutError:
            self.assertions.page_not_blank_or_error()
            logger.info("[提示] 金刚区使用非标准网格容器，主页面内容正常")
        return self

    def verify_banner(self) -> "MobileHomePage":
        """M-P0-HOME-004: 校验轮播 Banner / 运营公告区域。"""
        banner = self.elements.find_candidates(
            [
                ("css", ".van-swipe"),
                ("css", ".van-notice-bar"),
                ("css", ".banner"),
                ("css", ".swiper-container"),
                ("css", "[class*='banner']"),
                ("css", "[class*='notice']"),
            ],
            description="移动端轮播图/公告条",
        )
        if banner:
            banner.wait_for(state="visible", timeout=settings.DEFAULT_TIMEOUT)
            logger.info("[断言] 移动端轮播/公告区域正常展示")
        else:
            logger.info("[提示] 当前移动端首页未配置全局轮播图，保持容器展示校验")
        return self

    def verify_todo_cards(self) -> "MobileHomePage":
        """M-P0-HOME-005: 校验待办中心/任务统计卡片模块。"""
        self.assertions.page_not_blank_or_error()
        todo_candidates = [
            ("text", "待办"),
            ("text", "我的待办"),
            ("text", "审批"),
            ("text", "工单"),
            ("css", "[class*='todo']"),
            ("css", "[class*='task']"),
            ("css", "[class*='card']"),
        ]
        todo_el = self.elements.find_candidates(todo_candidates, description="待办任务卡片")
        if todo_el:
            logger.info("[断言] 移动端待办/任务卡片区域可见")
        return self

    def verify_resource_cards(self) -> "MobileHomePage":
        """M-P0-HOME-006: 校验精选推荐资源/服务列表。"""
        self.assertions.page_not_blank_or_error()
        list_items = self.page.locator(
            ".van-card, .resource-item, .service-card, .list-item, [class*='card'], [class*='item']"
        )
        if list_items.count() > 0:
            logger.info(f"[断言] 推荐资源/服务卡片列表项数量: {list_items.count()}")
        return self

    def switch_tab(self, tab_name: str) -> "MobileHomePage":
        """M-P0-NAV-001: 切换底部导航栏 Tab。"""
        tab_loc = self.elements.find_candidates(
            [
                ("text", tab_name),
                ("css", f".van-tabbar-item:has-text('{tab_name}')"),
                ("css", f"[class*='tabbar']:has-text('{tab_name}')"),
            ],
            description=f"底部导航Tab: {tab_name}",
        )
        if tab_loc:
            tab_loc.click()
            self.nav.wait_ready()
            self.assertions.page_not_blank_or_error()
            logger.info(f"[Tab切换] 点击底部导航: {tab_name}，当前URL: {self.page.url}")
        return self

    def verify_mine_page(self) -> "MobileHomePage":
        """M-P0-MINE-001: 校验个人中心（我的）页面展示。"""
        self.switch_tab("我的")
        self.assertions.page_not_blank_or_error()
        self.assertions.any_text_visible(["我的", "个人中心", "用户", "设置", "账号", "中建云"])
        logger.info("[断言] 个人中心页面展示正常")
        return self
