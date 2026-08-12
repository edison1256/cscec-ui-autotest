"""
运维巡检模块 fixtures

提供运维巡检模块特定的测试 fixtures：
- 巡检页面 Page Object
- 巡检项目数据
- 巡检记录模板
"""

import pytest

from config.settings import settings
from pages.ops.manual_inspection_page import ManualInspectionPage
from utils.data_loader import get_case_data, get_parametrize_data


# ────────────────────── Page Object Fixtures ──────────────────────

@pytest.fixture(scope="function")
def inspection_page(logged_in_page):
    """人工巡检页 Page Object"""
    return ManualInspectionPage(logged_in_page)


# ────────────────────── 测试数据 Fixtures ──────────────────────

@pytest.fixture(scope="module")
def inspection_data():
    """巡检测试数据"""
    return get_case_data("ops", "manual_inspection")


@pytest.fixture(scope="module")
def inspection_projects():
    """巡检项目列表"""
    return get_parametrize_data("ops", "manual_inspection", "projects")


@pytest.fixture(scope="module")
def inspection_items():
    """巡检项配置"""
    return get_parametrize_data("ops", "manual_inspection", "items")


# ────────────────────── 导航 Fixtures ──────────────────────

@pytest.fixture(scope="function")
def at_inspection_page(inspection_page):
    """导航到人工巡检页面"""
    inspection_page.nav.goto_url(settings.BASE_URL)
    inspection_page.navigate_from_menu()
    return inspection_page


# ────────────────────── 测试记录 Fixtures ──────────────────────

@pytest.fixture(scope="function")
def default_inspection_record(inspection_data):
    """默认巡检记录数据"""
    import time
    record = inspection_data.get("default_record", {}).copy()
    # 替换时间戳
    if "remark" in record:
        record["remark"] = record["remark"].replace("${TIMESTAMP}", str(int(time.time())))
    return record
