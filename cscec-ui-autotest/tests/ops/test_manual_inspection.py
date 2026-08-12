"""
人工巡检测试

测试场景：
- 巡检页面导航
- 巡检流程（选择项目、填写、保存）
"""

import pytest

from pages.portal.portal_home_page import PortalHomePage
from pages.ops.manual_inspection_page import ManualInspectionPage


@pytest.mark.ops
class TestManualInspection:
    """人工巡检测试"""

    @pytest.mark.regression
    @pytest.mark.readonly
    def test_inspection_page_accessible(self, logged_in_page):
        """测试巡检页面可访问"""
        portal = PortalHomePage(logged_in_page)
        portal.open()

        inspection = ManualInspectionPage(logged_in_page)
        inspection.navigate_from_menu()
        inspection.should_be_on_inspection_page()

    @pytest.mark.regression
    @pytest.mark.write
    def test_do_inspection(self, logged_in_page, default_inspection_record):
        """测试执行巡检流程"""
        portal = PortalHomePage(logged_in_page)
        portal.open()

        inspection = ManualInspectionPage(logged_in_page)
        inspection.navigate_from_menu()

        # 执行巡检（项目名需根据实际环境调整）
        inspection.do_inspection(
            project_name=default_inspection_record["project"],
            remark=default_inspection_record["remark"],
        )
        inspection.should_save_succeed()
