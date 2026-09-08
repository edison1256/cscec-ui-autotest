"""M0-D 文档中心只读走查补充用例（第四阶段深水区探活）。"""

from __future__ import annotations

import pytest

from core.navigation_helpers import EntryNotExposed
from pages.doccenter.doc_center_page import DocCenterPage


@pytest.mark.doccenter
@pytest.mark.readonly
@pytest.mark.regression
class TestDocCenterSupp:
    """M0-D 文档中心补充探活用例集。"""

    def test_m0d_supp_001_global_search(self, logged_in_page):
        """M0-D-SUPP-001: 全局知识库搜索路由与渲染。"""
        doc_page = DocCenterPage(logged_in_page)
        doc_page.open()
        doc_page.search_and_assert_results("中建云自动巡检边界关键字")

    def test_m0d_supp_002_doc_viewer_rendering(self, logged_in_page):
        """M0-D-SUPP-002: 富文本/Markdown 渲染引擎挂载。"""
        doc_page = DocCenterPage(logged_in_page)
        doc_page.open()
        try:
            doc_page.verify_doc_detail_rendering()
        except EntryNotExposed as exc:
            pytest.skip(str(exc))
