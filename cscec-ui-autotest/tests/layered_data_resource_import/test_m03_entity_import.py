"""M03 数据实体清单导入自动化测试用例集。

覆盖范围（依据《数据资源导入功能优化以及性能优化V2.xmind》）：
- M03-01: 数据实体清单导入弹窗与模板下载校验
- M03-02: 引用数据不匹配与必填字段缺失多行报错拦截
- M03-03: 数据实体重复「跳过」冲突模式校验
- M03-04: 数据实体重复「覆盖」冲突模式校验
- M03-05: 标准实体清单导入校验与数据资源列表英文名检索
"""

from __future__ import annotations

import pytest

from pages.dataresources.layered_import_page import LayeredImportPage


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
class TestM03EntityImport:
    """M03 数据实体清单导入用例集。"""

    def test_m03_01_import_dialog_and_template_check(self, layered_import_page: LayeredImportPage):
        """M03-01: 验证数据资源管理页导入数据实体清单弹窗正常打开，具备上传控件与模板下载。"""
        layered_import_page.open_m03_entity_import_dialog()
        layered_import_page.assertions.any_text_visible(["上传文件", "导入数据实体清单", "下载模板", "下载模版"])
        layered_import_page.close_import_dialog()

    def test_m03_02_multiple_error_rows_shows_error(self, layered_import_page: LayeredImportPage):
        """M03-02: 上传包含多行错误数据实体清单文件，断言提示多行错误信息且禁用导入。"""
        layered_import_page.open_m03_entity_import_dialog()
        # 对应测试文件：包含多行引用不匹配/异常实体数据
        layered_import_page.upload_file("M03数据实体清单 - 副本 - 副本.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.should_show_import_errors(["校验失败", "错误", "行"])
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m03_03_duplicate_entities_skip_mode(self, layered_import_page: LayeredImportPage):
        """M03-03: 上传包含重复数据实体清单文件，选择「重复跳过」模式进行校验。"""
        layered_import_page.open_m03_entity_import_dialog()
        layered_import_page.upload_file("M03数据实体清单 - 副本.xlsx")
        layered_import_page.select_conflict_mode("跳过")
        layered_import_page.click_validate_table()
        layered_import_page.assertions.page_not_blank_or_error()
        layered_import_page.close_import_dialog()

    def test_m03_04_duplicate_entities_overwrite_mode(self, layered_import_page: LayeredImportPage):
        """M03-04: 上传包含重复数据实体清单文件，选择「重复覆盖」模式进行校验。"""
        layered_import_page.open_m03_entity_import_dialog()
        layered_import_page.upload_file("M03数据实体清单 - 副本.xlsx")
        layered_import_page.select_conflict_mode("覆盖")
        layered_import_page.click_validate_table()
        layered_import_page.assertions.page_not_blank_or_error()
        layered_import_page.close_import_dialog()

    def test_m03_05_valid_import_and_search_entity(self, layered_import_page: LayeredImportPage):
        """M03-05: 上传标准有效 M03 实体清单校验，并在数据资源列表中按英文名检索实体。"""
        layered_import_page.open_m03_entity_import_dialog()
        layered_import_page.upload_file("M03数据实体清单.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.close_import_dialog()
        # 检索已导入的实体英文名
        layered_import_page.search_and_verify_entity("test0813table1")
