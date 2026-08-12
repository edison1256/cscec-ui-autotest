"""
文档中心模块 fixtures

提供文档中心模块特定的测试 fixtures：
- 文档中心页面 Page Object
- 文档测试数据
- 文件上传支持
"""

import pytest

from pages.doccenter.doc_center_page import DocCenterPage
from utils.data_loader import get_case_data, get_parametrize_data


# ────────────────────── Page Object Fixtures ──────────────────────

@pytest.fixture(scope="function")
def doc_center(logged_in_page):
    """文档中心 Page Object"""
    return DocCenterPage(logged_in_page)


# ────────────────────── 测试数据 Fixtures ──────────────────────

@pytest.fixture(scope="module")
def document_data():
    """文档操作测试数据"""
    return get_case_data("doccenter", "document")


@pytest.fixture(scope="module")
def categories_data():
    """文档分类数据"""
    return get_parametrize_data("doccenter", "categories")


@pytest.fixture(scope="module")
def workbench_data():
    """工作台测试数据"""
    return get_case_data("doccenter", "workbench")


@pytest.fixture(scope="module")
def upload_data():
    """文件上传测试数据"""
    return get_case_data("doccenter", "upload")


# ────────────────────── 导航 Fixtures ──────────────────────

@pytest.fixture(scope="function")
def at_doc_center(doc_center):
    """导航到文档中心页面"""
    doc_center.open()
    return doc_center


@pytest.fixture(scope="function")
def at_workbench(doc_center):
    """导航到工作台"""
    doc_center.open()
    doc_center.navigate_to_workspace()
    return doc_center


# ────────────────────── 测试文档 Fixtures ──────────────────────

@pytest.fixture(scope="function")
def new_document_data(document_data):
    """新建文档数据"""
    import time
    data = document_data.get("create", {}).copy()
    # 替换时间戳
    if "title" in data:
        data["title"] = data["title"].replace("${TIMESTAMP}", str(int(time.time())))
    if "content" in data:
        data["content"] = data["content"].replace("${TIMESTAMP}", str(int(time.time())))
    return data


@pytest.fixture(scope="function")
def test_file_path(tmp_path, upload_data):
    """
    创建测试用临时文件

    使用 pytest 的 tmp_path fixture 创建临时文件
    """
    test_file = tmp_path / "test_document.txt"
    test_file.write_text("这是自动化测试创建的文件内容", encoding="utf-8")
    return str(test_file)
