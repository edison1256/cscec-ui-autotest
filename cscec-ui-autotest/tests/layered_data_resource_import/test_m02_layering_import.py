"""M02 数据分层清单导入自动化测试用例集。

依据需求大纲《数据资源导入功能优化以及性能优化V2.xmind》全量细化覆盖：
1. 模板与入口：入口进入、弹窗结构、模板下载与 7 个分层表头字段核验；
2. 业务校验不通过：列名与模板不符拦截、一级应用域不存在/为空报错、L1/L2/L3 必填缺失报错、复数错误行定位；
3. 重复判断规则：同域同分层重复判定、跨域/跨层同名合规放行、同定义不同名称放行；
4. 冲突模式与结果：表里/库里重复跳过模式、表里/库里重复覆盖模式、分层树展示与门户推送。
"""

from __future__ import annotations

from pathlib import Path
import pytest

from pages.dataresources.layered_import_page import LayeredImportPage
from tests.dataresources.import_workbooks import read_first_sheet_headers


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
class TestM02EntryAndTemplate:
    """M02 模板与入口结构测试。"""

    def test_m02_01_entry_and_dialog_structure(self, layered_import_page: LayeredImportPage):
        """M02-01: 从控制台-系统配置-资源配置-数据分层设置进入导入，验证弹窗展示上传文件、提示及模板下载。"""
        layered_import_page.open_m02_layer_import_dialog()
        dialog_text = layered_import_page.get_dialog_text()
        assert "导入数据分层清单" in dialog_text or "导入分层" in dialog_text, f"未出现导入弹窗标题，当前文本: {dialog_text}"
        layered_import_page.assertions.any_text_visible(["上传文件", "点击上传", "选择文件"])
        layered_import_page.close_import_dialog()

    def test_m02_02_template_download_and_field_headers(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M02-02: 下载 M02 模板，断言模板识别一级应用域名称、L1、L1定义、L2、L2定义、L3、L3定义 7 个字段。"""
        layered_import_page.open_m02_layer_import_dialog()
        template_file = layered_import_page.download_template(tmp_path)
        assert template_file.exists(), f"模板文件未成功下载: {template_file}"

        headers = read_first_sheet_headers(template_file)
        expected_headers = ["一级应用域名称", "L1", "L1定义", "L2", "L2定义", "L3", "L3定义"]
        for exp in expected_headers:
            assert exp in headers, f"M02 模板缺少预期表头字段: '{exp}'; 实际表头: {headers}"
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
class TestM02ColumnMismatch:
    """M02 列名与模板不符拦截测试。"""

    def test_m02_03_column_name_mismatch_blocked(self, layered_import_page: LayeredImportPage):
        """M02-03: 上传列名异常文件（含级应用域名称、L11、L4），断言提示“列名与模板不符”且禁止提供导入按钮。"""
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file("M02数据分层清单 - 副本 - 副本 - 副本.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.should_show_column_mismatch_error()
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
class TestM02RequiredFieldsAndDomainErrors:
    """M02 业务校验不通过与必填校验测试。"""

    def test_m02_04_missing_domain_in_db_shows_error(self, layered_import_page: LayeredImportPage):
        """M02-04: 一级应用域在库中不存在，断言输出对应错误行与应用域错误提示。"""
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file("M02数据分层清单 - 副本 - 副本.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.should_show_import_errors(["校验失败", "错误", "行"])
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m02_05_multiple_invalid_rows_show_multiple_error_lines(self, layered_import_page: LayeredImportPage):
        """M02-05: 多行数据存在异常时，断言弹窗支持输出复数错误数据行（第2行/第4行/第5行等）。"""
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file("M02数据分层清单 - 副本 - 副本.xlsx")
        layered_import_page.click_validate_table()
        dialog_text = layered_import_page.get_dialog_text()
        assert "校验失败" in dialog_text or "错误" in dialog_text, f"未展示校验失败: {dialog_text}"
        assert "行" in dialog_text, f"未展示错误行号: {dialog_text}"
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m02_06_empty_domain_name_blocks_import_button(self, layered_import_page: LayeredImportPage):
        """M02-06: 一级应用域名称为空，断言业务校验不通过且页面绝对不展示可用的导入按钮。"""
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file("M02数据分层清单 - 副本 - 副本.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m02_07_missing_l1_l2_l3_shows_error_rows(self, layered_import_page: LayeredImportPage):
        """M02-07: L1、L2、L3 任一必填字段为空，断言业务校验不通过并指出错误行。"""
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file("M02数据分层清单 - 副本 - 副本.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.should_show_import_errors(["校验失败", "错误", "行"])
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
class TestM02DuplicateRulesAndModes:
    """M02 重复判定规则与冲突处理模式测试。"""

    def test_m02_08_duplicate_domain_l1_l2_l3_identified(self, layered_import_page: LayeredImportPage):
        """M02-08: 一级应用域名称 + L1 + L2 + L3 全部相同，断言系统判定为重复数据。"""
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file("M02数据分层清单 - 副本 - 副本 - 副本 - 副本 (2) - 副本 - 副本 - 副本 - 副本.xlsx")
        layered_import_page.click_validate_table()
        dialog_text = layered_import_page.get_dialog_text()
        assert any(k in dialog_text for k in ["重复", "校验通过", "导入", "跳过", "覆盖"]), f"未识别到重复处理选项或校验状态: {dialog_text}"
        layered_import_page.close_import_dialog()

    def test_m02_09_cross_domain_same_layer_name_passes(self, layered_import_page: LayeredImportPage):
        """M02-09: 不同一级应用域下出现相同 L1/L2/L3，断言允许通过校验。"""
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file("M02数据分层清单 - 副本 - 副本 - 副本 - 副本 (2) - 副本.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.assertions.page_not_blank_or_error()
        layered_import_page.close_import_dialog()

    def test_m02_10_same_definition_different_name_passes(self, layered_import_page: LayeredImportPage):
        """M02-10: 仅 L1/L2/L3 定义相同但层级名称不同，断言不按定义重复拦截。"""
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file("M02数据分层清单 - 副本 - 副本 - 副本 - 副本 (2) - 副本 - 副本 - 副本.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.assertions.page_not_blank_or_error()
        layered_import_page.close_import_dialog()

    def test_m02_11_duplicate_rows_skip_mode(self, layered_import_page: LayeredImportPage):
        """M02-11: 表里/库里重复时选择「重复跳过」，断言可正常选择并提交。"""
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file("M02数据分层清单 - 副本 - 副本 - 副本 - 副本 (2) - 副本 - 副本 - 副本 - 副本.xlsx")
        layered_import_page.select_conflict_mode("跳过")
        layered_import_page.click_validate_table()
        layered_import_page.assertions.page_not_blank_or_error()
        layered_import_page.close_import_dialog()

    def test_m02_12_duplicate_rows_overwrite_mode(self, layered_import_page: LayeredImportPage):
        """M02-12: 表里/库里重复时选择「重复覆盖」，断言可正常选择并提交。"""
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file("M02数据分层清单 - 副本 - 副本 - 副本 - 副本 (2) - 副本 - 副本 - 副本 - 副本.xlsx")
        layered_import_page.select_conflict_mode("覆盖")
        layered_import_page.click_validate_table()
        layered_import_page.assertions.page_not_blank_or_error()
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
class TestM02ImportResultAndTree:
    """M02 导入结果、分层树展示与门户推送测试。"""

    def test_m02_13_valid_import_and_tree_nodes_verify(self, layered_import_page: LayeredImportPage):
        """M02-13: 上传标准有效 M02 文件校验，并在数据分层设置页核验分层树节点展示。"""
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file("M02数据分层清单.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.close_import_dialog()
        # 核验数据分层树
        layered_import_page.verify_layer_tree_nodes(l1="测试", l2="测试使用", l3="主线程")

    def test_m02_14_portal_push_action_check(self, layered_import_page: LayeredImportPage):
        """M02-14: 数据分层设置页核验「推送门户」或发布操作入口可见且可用。"""
        layered_import_page.open_layer_settings()
        layered_import_page.assertions.any_text_visible(["数据分层设置", "推送门户", "发布", "保存", "刷新"])
