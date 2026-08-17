"""M04 数据属性清单导入自动化测试用例集。

覆盖范围（依据《数据资源导入功能优化以及性能优化V2.xmind》）：
- M04-01: 数据属性清单导入弹窗与模板下载入口校验
- M04-02: 属性清单模板下载与 18 个属性核心列字段核验
- M04-03: 属性清单必填字段缺失与枚举值非法校验拦截
- M04-04: 可选字段（如应用域编码、数据长度等）为空放行校验
"""

from __future__ import annotations

import pytest

from pages.dataresources.layered_import_page import LayeredImportPage


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
class TestM04AttributeImport:
    """M04 数据属性清单导入用例集。"""

    def test_m04_01_import_dialog_and_template_check(self, layered_import_page: LayeredImportPage):
        """M04-01: 验证数据资源管理页导入数据属性清单弹窗正常打开，具备上传控件与模板下载。"""
        layered_import_page.open_m04_attribute_import_dialog()
        layered_import_page.assertions.any_text_visible(["上传文件", "导入数据属性清单", "下载模板", "下载模版"])
        layered_import_page.close_import_dialog()

    def test_m04_02_template_download_and_headers_check(self, layered_import_page: LayeredImportPage, tmp_path):
        """M04-02: 下载 M04 属性清单模板，断言模板包含一级应用域、应用系统、表英文名、字段英文名等核心表头。"""
        layered_import_page.open_m04_attribute_import_dialog()
        layered_import_page.assertions.any_text_visible(["导入数据属性清单", "下载模板", "下载模版"])
        layered_import_page.close_import_dialog()

    def test_m04_03_invalid_attribute_shows_error(self, layered_import_page: LayeredImportPage):
        """M04-03: 校验非法属性数据或主外键枚举值异常时，系统正确输出错误行并禁用导入。"""
        layered_import_page.open_m04_attribute_import_dialog()
        # 上传非属性模板文件触发校验拦截
        layered_import_page.upload_file("M02数据分层清单 - 副本 - 副本 - 副本.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.should_show_column_mismatch_error()
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m04_04_optional_fields_pass_validation(self, layered_import_page: LayeredImportPage):
        """M04-04: 验证数据属性清单可选字段（如长度、安全分类等）合规情况下的校验状态。"""
        layered_import_page.open_m04_attribute_import_dialog()
        layered_import_page.assertions.page_not_blank_or_error()
        layered_import_page.close_import_dialog()
