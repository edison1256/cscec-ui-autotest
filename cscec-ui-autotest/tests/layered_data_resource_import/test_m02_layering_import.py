"""M02 数据分层清单导入自动化测试用例集。

覆盖范围（依据《数据资源导入功能优化以及性能优化V2.xmind》）：
- M02-01: 导入弹窗与模板下载入口校验
- M02-02: 模板列名不符业务校验与拦截（禁止提供导入按钮）
- M02-03: 一级应用域/必填层级缺失多行错误识别与拦截
- M02-04: 重复分层数据「跳过」冲突模式校验
- M02-05: 重复分层数据「覆盖」冲突模式校验
- M02-06: 标准分层清单导入与分层树结构节点呈现
"""

from __future__ import annotations

import pytest

from pages.dataresources.layered_import_page import LayeredImportPage


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
class TestM02LayeringImport:
    """M02 数据分层清单导入用例集。"""

    def test_m02_01_import_dialog_and_template_check(self, layered_import_page: LayeredImportPage):
        """M02-01: 验证数据分层设置页导入弹窗正常打开，具备上传控件与模板下载。"""
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.assertions.any_text_visible(["上传文件", "导入数据分层清单", "下载模板", "下载模版"])
        layered_import_page.close_import_dialog()

    def test_m02_02_column_name_mismatch_blocked(self, layered_import_page: LayeredImportPage):
        """M02-02: 上传列名与模板不符文件，断言提示“列名与模板不符”且不提供可点击的导入按钮。"""
        layered_import_page.open_m02_layer_import_dialog()
        # 对应测试文件：表头为异常列名（级应用域名称、L11、L4）
        layered_import_page.upload_file("M02数据分层清单 - 副本 - 副本 - 副本.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.should_show_column_mismatch_error()
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m02_03_missing_domain_and_layers_shows_error_rows(self, layered_import_page: LayeredImportPage):
        """M02-03: 上传一级应用域与必填层级缺失的文件，断言多行报错且导入按钮被禁用。"""
        layered_import_page.open_m02_layer_import_dialog()
        # 对应测试文件：包含缺失一级应用域、缺L1、缺L2、缺L3的多行异常数据
        layered_import_page.upload_file("M02数据分层清单 - 副本 - 副本.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.should_show_import_errors(["校验失败", "错误", "行"])
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m02_04_duplicate_rows_skip_mode(self, layered_import_page: LayeredImportPage):
        """M02-04: 上传包含重复层级的数据文件，选择「重复跳过」模式进行校验。"""
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file("M02数据分层清单 - 副本 - 副本 - 副本 - 副本 (2) - 副本 - 副本 - 副本 - 副本.xlsx")
        layered_import_page.select_conflict_mode("跳过")
        layered_import_page.click_validate_table()
        layered_import_page.assertions.page_not_blank_or_error()
        layered_import_page.close_import_dialog()

    def test_m02_05_duplicate_rows_overwrite_mode(self, layered_import_page: LayeredImportPage):
        """M02-05: 上传包含重复层级的数据文件，选择「重复覆盖」模式进行校验。"""
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file("M02数据分层清单 - 副本 - 副本 - 副本 - 副本 (2) - 副本 - 副本 - 副本 - 副本.xlsx")
        layered_import_page.select_conflict_mode("覆盖")
        layered_import_page.click_validate_table()
        layered_import_page.assertions.page_not_blank_or_error()
        layered_import_page.close_import_dialog()

    def test_m02_06_valid_import_and_tree_verify(self, layered_import_page: LayeredImportPage):
        """M02-06: 上传标准有效 M02 文件校验，并在数据分层设置页核验分层树节点结构。"""
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file("M02数据分层清单.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.close_import_dialog()
        # 核验分层树节点
        layered_import_page.verify_layer_tree_nodes(l1="测试", l2="测试使用", l3="主线程")
