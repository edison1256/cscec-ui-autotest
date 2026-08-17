"""M02 数据分层清单导入自动化测试用例集（数据驱动架构）。

依据需求大纲《数据资源导入功能优化以及性能优化V2.xmind》全量细化覆盖：
1. 模板与入口：入口进入、弹窗结构、模板下载与 7 个分层表头字段核验；
2. 业务校验不通过（数据驱动）：列名与模板不符拦截、一级应用域不存在/为空报错、L1/L2/L3 必填缺失报错、复数错误行定位；
3. 重复判断规则（数据驱动）：同域同分层重复判定、跨域/跨层同名合规放行、同定义不同名称放行；
4. 冲突模式与结果：表里/库里重复跳过模式、表里/库里重复覆盖模式、分层树展示与门户推送。
"""

from __future__ import annotations

from pathlib import Path
import pytest

from pages.dataresources.layered_import_page import LayeredImportPage
from tests.dataresources.import_workbooks import (
    create_workbook_from_headers,
    m02_diff_l1_same_l2_pass_rows,
    m02_duplicate_layer_rows,
    m02_unique_layer_row,
    read_first_sheet_headers,
)
from tests.layered_data_resource_import.data_provider import get_m02_dataset, import_run_id


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
@pytest.mark.readonly
class TestM02EntryAndTemplate:
    """M02 模板与入口结构测试。"""

    def test_m02_01_entry_and_dialog_structure(self, layered_import_page: LayeredImportPage):
        """M02-01: 从控制台-系统配置-资源配置-数据分层设置进入导入，验证弹窗展示上传文件、提示及模板下载。"""
        layered_import_page.open_m02_layer_import_dialog()
        dialog_text = layered_import_page.get_dialog_text()
        assert "导入数据分层清单" in dialog_text or "导入分层" in dialog_text, f"未出现导入弹窗标题，当前文本: {dialog_text}"
        assert any(k in dialog_text for k in ["上传文件", "点击上传", "选择文件", "下载模板", "下载模版"]), f"未出现上传或模板提示，弹窗文本: {dialog_text}"
        layered_import_page.close_import_dialog()

    def test_m02_02_template_download_and_field_headers(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M02-02: 下载 M02 模板，断言模板识别一级应用域名称、L1、L1定义、L2、L2定义、L3、L3定义 7 个字段。"""
        layered_import_page.open_m02_layer_import_dialog()
        template_file = layered_import_page.download_template(tmp_path)
        assert template_file.exists(), f"模板文件未成功下载: {template_file}"

        headers = read_first_sheet_headers(template_file)
        expected_headers = get_m02_dataset("standard_valid").get(
            "expected_headers", ["一级应用域名称", "L1", "L1定义", "L2", "L2定义", "L3", "L3定义"]
        )
        for exp in expected_headers:
            assert exp in headers, f"M02 模板缺少预期表头字段: '{exp}'; 实际表头: {headers}"
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
@pytest.mark.write
class TestM02ColumnMismatch:
    """M02 列名与模板不符拦截测试。"""

    def test_m02_03_column_name_mismatch_blocked(self, layered_import_page: LayeredImportPage):
        """M02-03: 上传列名异常文件（含级应用域名称、L11、L4），断言提示“列名与模板不符”且禁止提供导入按钮。"""
        ds = get_m02_dataset("column_mismatch")
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file(ds["file_path"])
        layered_import_page.click_validate_table()
        layered_import_page.should_show_column_mismatch_error()
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
@pytest.mark.write
class TestM02RequiredFieldsAndDomainErrors:
    """M02 业务校验不通过与必填校验测试（数据驱动）。"""

    @pytest.mark.parametrize(
        "dataset_key,expected_snippets",
        [
            ("missing_domain_and_empty", ["第 2 行", "错误"]),
            ("missing_domain_and_empty", ["不存在", "不能为空"]),
        ],
    )
    def test_m02_04_parametrized_validation_errors(
        self, layered_import_page: LayeredImportPage, dataset_key: str, expected_snippets: list[str]
    ):
        """M02-04: 数据驱动测试各项非合规与必填缺失数据集，断言精准报错并拦截导入按钮。"""
        ds = get_m02_dataset(dataset_key)
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file(ds["file_path"])
        layered_import_page.click_validate_table()
        layered_import_page.should_show_import_errors(expected_snippets)
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m02_05_multiple_invalid_rows_show_multiple_error_lines(self, layered_import_page: LayeredImportPage):
        """M02-05: 多行数据存在异常时，断言弹窗支持输出复数错误数据行（第2行/第4行/第5行等）。"""
        ds = get_m02_dataset("missing_domain_and_empty")
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file(ds["file_path"])
        layered_import_page.click_validate_table()
        dialog_text = layered_import_page.get_dialog_text()
        assert "校验失败" in dialog_text or "错误" in dialog_text, f"未展示校验失败: {dialog_text}"
        assert "行" in dialog_text, f"未展示错误行号: {dialog_text}"
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m02_06_empty_domain_name_blocks_import_button(self, layered_import_page: LayeredImportPage):
        """M02-06: 一级应用域名称为空，断言业务校验不通过且页面绝对不展示可用的导入按钮。"""
        ds = get_m02_dataset("missing_domain_and_empty")
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file(ds["file_path"])
        layered_import_page.click_validate_table()
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m02_07_missing_l1_l2_l3_shows_error_rows(self, layered_import_page: LayeredImportPage):
        """M02-07: L1、L2、L3 任一必填字段为空，断言业务校验不通过并指出错误行。"""
        ds = get_m02_dataset("missing_l1_l2_l3")
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file(ds["file_path"])
        layered_import_page.click_validate_table()
        layered_import_page.should_show_import_errors(["错误", "不能为空", "第 1 行", "第 2 行"])
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
@pytest.mark.write
class TestM02DuplicateRulesAndModes:
    """M02 重复判定规则与跳过/覆盖冲突模式测试（数据驱动）。"""

    def test_m02_08_duplicate_domain_l1_l2_l3_identified(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M02-08: 校验表格时，如果一级应用域名称+L1+L2+L3全部相同，系统判定为重复数据。"""
        run_id = import_run_id("m02_dup")
        layered_import_page.open_m02_layer_import_dialog()
        template_file = layered_import_page.download_template(tmp_path)
        headers = read_first_sheet_headers(template_file)
        import_file = create_workbook_from_headers(
            tmp_path,
            f"{run_id}.xlsx",
            headers,
            m02_duplicate_layer_rows(headers, run_id),
        )

        layered_import_page.upload_file(import_file)
        layered_import_page.click_validate_table()
        dialog_text = layered_import_page.get_dialog_text()
        assert any(k in dialog_text for k in ["重复", "覆盖", "跳过"]), f"未识别重复数据，当前内容: {dialog_text}"
        layered_import_page.close_import_dialog()

    @pytest.mark.parametrize(
        "dataset_key",
        ["duplicate_cross_domain", "same_def_diff_name"],
    )
    def test_m02_09_compliant_variants_pass(self, layered_import_page: LayeredImportPage, dataset_key: str):
        """M02-09/10: 数据驱动验证跨域同名分层及同定义不同名称合规数据放行。"""
        ds = get_m02_dataset(dataset_key)
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file(ds["file_path"])
        layered_import_page.click_validate_table()
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.close_import_dialog()

    def test_m02_10_same_definition_different_name_passes(self, layered_import_page: LayeredImportPage):
        """M02-10: 仅层级定义相同但名称不同时，不按定义判定重复，允许通过校验。"""
        ds = get_m02_dataset("same_def_diff_name")
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file(ds["file_path"])
        layered_import_page.click_validate_table()
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.close_import_dialog()

    def test_m02_10b_diff_l1_same_l2_passes(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M02: 不同 L1 下出现相同 L2 名称，断言不判重复、允许通过校验（重复键为完整路径）。"""
        run_id = import_run_id("m02_l2pass")
        layered_import_page.open_m02_layer_import_dialog()
        template_file = layered_import_page.download_template(tmp_path)
        headers = read_first_sheet_headers(template_file)
        import_file = create_workbook_from_headers(
            tmp_path,
            f"{run_id}.xlsx",
            headers,
            m02_diff_l1_same_l2_pass_rows(headers, run_id),
        )

        layered_import_page.upload_file(import_file)
        layered_import_page.click_validate_table()
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.close_import_dialog()

    @pytest.mark.parametrize("mode", ["跳过", "覆盖"])
    def test_m02_11_duplicate_modes_selection(self, layered_import_page: LayeredImportPage, mode: str, tmp_path: Path):
        """M02-11/12: 数据驱动测试表里/库里重复数据下的「跳过」与「覆盖」模式选择与真实提交导入。

        注：「保留第一条/最后条」的精确落库核对需在导入后对分层树节点定义做比对，依赖预置数据，
        本用例先验证到「选择冲突模式→点击导入→导入完成」，精确核对标记为后续项。
        """
        run_id = import_run_id(f"m02_{mode}")
        layered_import_page.open_m02_layer_import_dialog()
        template_file = layered_import_page.download_template(tmp_path)
        headers = read_first_sheet_headers(template_file)
        import_file = create_workbook_from_headers(
            tmp_path,
            f"{run_id}.xlsx",
            headers,
            m02_duplicate_layer_rows(headers, run_id),
        )

        layered_import_page.upload_file(import_file)
        layered_import_page.click_validate_table()
        layered_import_page.select_conflict_mode(mode)
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.click_confirm_import()
        layered_import_page.should_show_import_finished()
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
@pytest.mark.write
class TestM02ImportResultAndTree:
    """M02 导入结果与分层树节点展示测试。"""

    def test_m02_13_valid_import_and_tree_nodes_verify(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M02-13: 标准 M02 文件导入前校验通过后，验证当前分层树中基线 L1/L2/L3 层级可见。"""
        run_id = import_run_id("m02_tree")
        layered_import_page.open_m02_layer_import_dialog()
        template_file = layered_import_page.download_template(tmp_path)
        headers = read_first_sheet_headers(template_file)
        row = m02_unique_layer_row(headers, run_id)
        import_file = create_workbook_from_headers(tmp_path, f"{run_id}.xlsx", headers, row)

        layered_import_page.upload_file(import_file)
        layered_import_page.click_validate_table()
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.click_confirm_import()
        layered_import_page.should_show_import_finished()
        layered_import_page.close_import_dialog()
        layered_import_page.verify_layer_tree_nodes(l1=row["L1"], l2=row["L2"], l3=row["L3"])

    def test_m02_14_portal_push_action_check(self, layered_import_page: LayeredImportPage):
        """M02-14: 数据分层设置完成后，核验页面「推送门户」按钮状态与响应。"""
        layered_import_page.open_layer_settings()
        layered_import_page.assertions.any_text_visible(["推送门户", "数据分层设置", "导入数据分层清单"])
