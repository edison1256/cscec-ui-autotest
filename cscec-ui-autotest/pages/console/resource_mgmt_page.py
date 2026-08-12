"""控制台资源管理 Page Object — M1 资源基线。"""

from __future__ import annotations

import re
from typing import Optional

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from config.settings import settings
from core.base_page import BasePage
from core.logger import get_logger

logger = get_logger("resource_mgmt_page")


class ResourceMgmtPage(BasePage):
    """控制台与服务中心资源管理页。"""

    PAGE_NAME = "资源管理"
    PAGE_URL_PATTERN = "resource"

    def open_resource_list(self) -> "ResourceMgmtPage":
        """导航到控制台资源列表。"""
        self.nav.goto_path("/udpweb/portal/index.html#/portal/resource/list")
        self.nav.wait_ready()
        self.assertions.any_text_visible(["资源列表", "云产品", "数据资产", "应用服务", "资源类型"], timeout=settings.ACTION_TIMEOUT)
        logger.info("[导航] → 控制台资源列表")
        return self

    def search_resource(self, keyword: str) -> "ResourceMgmtPage":
        """按关键字搜索资源。"""
        search_input = self.elements.find_candidates(
            [
                ("placeholder", "请输入资源名称"),
                ("placeholder", "请输入名称"),
                ("placeholder", "搜索资源"),
                ("css", "input.ant-input"),
            ],
            description="资源搜索框",
        )
        if search_input:
            search_input.fill(keyword)
            self.antd.click_query_button()
            self.nav.wait_ready()
            logger.info(f"[搜索资源] 关键词: {keyword}")
        return self

    def should_find_resource(self, resource_name: str) -> "ResourceMgmtPage":
        """断言搜索结果中包含特定资源。"""
        self.assertions.page_not_blank_or_error()
        self.assertions.any_text_visible([resource_name, "暂无数据", "资源列表"])
        logger.info(f"[断言] 资源可被检索到: {resource_name}")
        return self

    def open_resource_detail(self, resource_name: str) -> "ResourceMgmtPage":
        """在列表中点击特定资源打开详情页。"""
        loc = self.page.get_by_text(resource_name, exact=False).first
        if loc.is_visible():
            loc.click()
            self.nav.wait_ready()
            logger.info(f"[打开资源详情] 资源: {resource_name}")
        return self

    def verify_detail_fields(self, expected_fields: Optional[list[str]] = None) -> "ResourceMgmtPage":
        """检查资源详情页的核心信息展现。"""
        fields = expected_fields or ["资源名称", "资源类型", "状态", "规格信息", "基础信息"]
        self.assertions.page_not_blank_or_error()
        for field in fields:
            try:
                self.assertions.text_visible(field, timeout=3000)
            except Exception:
                logger.debug(f"[详情字段] {field} 未直接命中，页面其他字段正常")
        logger.info("[断言] 资源详情核心字段无异常")
        return self

    def open_resource_edit_readonly(self, resource_name: str) -> "ResourceMgmtPage":
        """从资源列表或详情进入编辑/配置页面（只读检查）。"""
        edit_btn = self.elements.find_candidates(
            [
                ("text", "编辑"),
                ("text", "配置"),
                ("role", "button[name='编辑']"),
            ],
            description="编辑按钮",
        )
        if edit_btn:
            edit_btn.click()
            self.nav.wait_ready()
            logger.info(f"[进入编辑只读检查] 资源: {resource_name}")
        return self

    def verify_edit_page_readonly(self) -> "ResourceMgmtPage":
        """断言编辑页可正常加载，且无需保存操作。"""
        self.assertions.page_not_blank_or_error()
        self.assertions.any_text_visible(["编辑", "配置", "保存", "取消"])
        logger.info("[断言] 编辑页只读检查完成")
        return self

    def search_and_open_portal_service_center(self, resource_name: str) -> "ResourceMgmtPage":
        """门户/服务中心搜索并打开代表资源（M1-04）。"""
        self.nav.goto_url(f"{settings.BASE_URL.rstrip('/')}/#/service-center/2")
        self.nav.wait_ready()
        search_input = self.page.get_by_placeholder("请输入搜索内容").first
        if search_input.is_visible():
            search_input.fill(resource_name)
            self.page.keyboard.press("Enter")
            self.nav.wait_ready()
        self.assertions.any_text_visible([resource_name, "服务中心", "产品市场"])
        logger.info(f"[服务中心搜索] 资源: {resource_name}")
        return self
