"""
文档中心测试

测试场景：
- 文档中心页面可访问
- 工作台可访问
- 我的文档导航
"""

import pytest

from pages.doccenter.doc_center_page import DocCenterPage


@pytest.mark.doccenter
@pytest.mark.readonly
class TestDocCenter:
    """文档中心测试"""

    @pytest.mark.smoke
    def test_doc_center_accessible(self, logged_in_page):
        """测试文档中心页面可访问"""
        doc_center = DocCenterPage(logged_in_page)
        doc_center.open()
        doc_center.should_be_on_doc_center()

    @pytest.mark.smoke
    def test_workspace_visible(self, logged_in_page):
        """测试工作台可见"""
        doc_center = DocCenterPage(logged_in_page)
        doc_center.open()
        doc_center.should_be_on_doc_center()
        doc_center.should_see_workspace()

    @pytest.mark.regression
    def test_navigate_to_my_documents(self, logged_in_page):
        """测试导航到我的文档"""
        doc_center = DocCenterPage(logged_in_page)
        doc_center.open()
        doc_center.navigate_to_my_documents()
        doc_center.nav.wait_for_url_contains("mydoc")
        doc_center.assertions.text_visible("我的文档")
