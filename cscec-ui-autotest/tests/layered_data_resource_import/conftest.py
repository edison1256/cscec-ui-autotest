"""分层数据资源导入测试套件专属夹具与配置。"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Page

from pages.dataresources.layered_import_page import LayeredImportPage

# 测试数据文件夹
TEST_DATA_DIR = Path(r"C:\Users\CFD\Desktop\260812")


@pytest.fixture(scope="session")
def test_import_data_dir() -> Path:
    """提供测试导入文件根目录。"""
    assert TEST_DATA_DIR.exists(), f"测试导入数据目录不存在: {TEST_DATA_DIR}"
    return TEST_DATA_DIR


@pytest.fixture
def layered_import_page(logged_in_page: Page) -> LayeredImportPage:
    """初始化已登录状态下的 LayeredImportPage 页面对象（自动从控制台页签进入）。"""
    from pages.portal.portal_home_page import PortalHomePage
    portal = PortalHomePage(logged_in_page)
    portal.open()
    console_page = portal.open_console_page()
    page_obj = LayeredImportPage(console_page)
    yield page_obj
    if not console_page.is_closed():
        console_page.close()
