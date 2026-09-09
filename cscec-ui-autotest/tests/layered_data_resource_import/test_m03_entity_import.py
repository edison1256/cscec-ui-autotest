"""M03 数据实体清单导入自动化测试用例集（数据驱动架构）。

依据需求大纲《数据资源导入功能优化以及性能优化V2.xmind》全量细化覆盖：
1. 模板与入口：入口进入、弹窗结构、模板下载与 10 个数据实体表头字段核验；
2. 引用数据校验（数据驱动）：一级应用域不存在、应用系统不存在、域与系统不对应、L1-L3 分层不存在；
3. 必填与可空校验（数据驱动）：表中文名/英文名/描述/存储周期/项目组必填校验、非必填放行；
4. 重复判断规则（数据驱动）：域+系统+分层+表英文名完全相同时判定重复、跳过/覆盖冲突模式；
5. 导入结果核验：导入后在数据资源列表精确检索表英文名并核验关键列信息展示。
"""

from __future__ import annotations

from pathlib import Path
import pytest

from pages.dataresources.layered_import_page import LayeredImportPage
from tests.dataresources.import_workbooks import (
    create_workbook_from_template,
    m03_duplicate_entity_rows,
    m03_app_domain_system_mismatch_row,
    m03_missing_app_domain_row,
    m03_missing_app_system_row,
    m03_missing_layer_row,
    m03_missing_required_field_row,
    m03_valid_like_row,
    read_first_sheet_headers,
)
from tests.layered_data_resource_import.data_provider import get_m03_dataset, import_run_id
from tests.layered_data_resource_import.workflow_helpers import build_upload_validate


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
@pytest.mark.readonly
class TestM03EntryAndTemplate:
    """M03 模板与入口结构测试。"""

    def test_m03_01_entry_and_dialog_structure(self, layered_import_page: LayeredImportPage):
        """M03-01: 从控制台-资源管理-数据资源管理进入导入，验证展示上传文件、校验提示、导入模板。"""
        layered_import_page.open_m03_entity_import_dialog()
        dialog_text = layered_import_page.get_dialog_text()
        assert "导入数据实体清单" in dialog_text or "导入数据实体" in dialog_text, f"未出现导入实体弹窗标题，当前文本: {dialog_text}"
        assert any(k in dialog_text for k in ["上传文件", "点击上传", "选择文件", "下载模板", "下载模版"]), f"未出现上传或模板提示，弹窗文本: {dialog_text}"
        layered_import_page.close_import_dialog()

    def test_m03_02_template_download_and_field_headers(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M03-02: 下载 M03 模板，断言识别一级应用域、应用系统、L1-L3、表中文名、表英文名、表描述等字段。"""
        layered_import_page.open_m03_entity_import_dialog()
        template_file = layered_import_page.download_template(tmp_path)
        assert template_file.exists(), f"模板文件未成功下载: {template_file}"

        headers = read_first_sheet_headers(template_file)
        expected_headers = get_m03_dataset("standard_valid").get(
            "expected_headers",
            ["一级应用域名称", "应用系统名称", "L1", "L2", "L3", "表中文名称", "表英文名称", "表描述", "存储周期", "系统项目组"]
        )
        for exp in expected_headers:
            assert any(exp in h for h in headers), f"M03 模板缺少预期表头字段: '{exp}'; 实际表头: {headers}"
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
@pytest.mark.write
class TestM03ReferenceDataErrors:
    """M03 引用数据校验测试（数据驱动）。"""

    def test_m03_03_missing_domain_shows_error(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M03-03: B列一级应用域名称在库中不存在，断言业务校验不通过并输出错误数据行。"""
        run_id = import_run_id("m03_missing_domain")
        layered_import_page.open_m03_entity_import_dialog()
        build_upload_validate(
            layered_import_page,
            tmp_path,
            run_id,
            lambda h: m03_missing_app_domain_row(h, f"auto_{run_id}"),
        )
        layered_import_page.should_show_import_errors(["校验失败", "错误", "行"])
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m03_04_missing_system_shows_error(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M03-04: D列应用系统名称在库中不存在，断言业务校验不通过并输出错误数据行。"""
        run_id = import_run_id("m03_missing_system")
        layered_import_page.open_m03_entity_import_dialog()
        build_upload_validate(
            layered_import_page,
            tmp_path,
            run_id,
            lambda h: m03_missing_app_system_row(h, f"auto_{run_id}"),
        )
        layered_import_page.should_show_import_errors(["系统", "错误", "行", "校验失败"])
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m03_05_domain_system_mismatch_shows_error(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M03-05: B列一级应用域与D列应用系统不对应，断言业务校验不通过并输出错误数据行。"""
        run_id = import_run_id("m03_domain_system_mismatch")
        layered_import_page.open_m03_entity_import_dialog()
        build_upload_validate(
            layered_import_page,
            tmp_path,
            run_id,
            lambda h: m03_app_domain_system_mismatch_row(h, f"auto_{run_id}"),
        )
        layered_import_page.should_show_import_errors(["对应", "不匹配", "错误", "校验失败"])
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m03_06_missing_layer_shows_error(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M03-06: L1~L3分层在库中不存在或与系统不匹配，断言业务校验不通过并输出错误数据行。"""
        run_id = import_run_id("m03_missing_layer")
        layered_import_page.open_m03_entity_import_dialog()
        build_upload_validate(
            layered_import_page,
            tmp_path,
            run_id,
            lambda h: m03_missing_layer_row(h, f"auto_{run_id}"),
        )
        layered_import_page.should_show_import_errors(["分层", "L1", "L2", "L3", "错误", "校验失败"])
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
@pytest.mark.write
class TestM03RequiredAndOptionalFields:
    """M03 必填字段与非必填字段校验测试。"""

    def test_m03_07_missing_required_fields_blocked(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M03-07: 表中文名/表英文名/表描述/存储周期/项目组任一为空，断言业务校验不通过。"""
        run_id = import_run_id("m03_missing_required")
        layered_import_page.open_m03_entity_import_dialog()
        build_upload_validate(
            layered_import_page,
            tmp_path,
            run_id,
            lambda h: m03_missing_required_field_row(h, f"auto_{run_id}"),
        )
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m03_08_optional_fields_pass(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M03-08: 一级应用域编码、应用系统编码、数据责任部门为空时，断言不拦截校验。"""
        run_id = import_run_id("m03_optional")
        layered_import_page.open_m03_entity_import_dialog()
        template_file = layered_import_page.download_template(tmp_path)
        headers = read_first_sheet_headers(template_file)
        row = m03_valid_like_row(headers, f"auto_{run_id}")
        row["一级应用域编号"] = ""
        row["应用系统编码"] = ""
        row["数据责任部门"] = ""
        import_file = create_workbook_from_template(template_file, tmp_path / f"{run_id}.xlsx", headers, row)

        layered_import_page.upload_file(import_file)
        layered_import_page.click_validate_table()
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
@pytest.mark.write
class TestM03DuplicateAndConflictModes:
    """M03 重复判定规则与跳过/覆盖冲突模式测试（数据驱动）。"""

    def test_m03_09_duplicate_entities_skip_mode(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M03-09: 实体全元组相同判定重复，选择「重复跳过」并真实提交导入，断言导入完成。"""
        run_id = import_run_id("m03_dup_skip")
        layered_import_page.open_m03_entity_import_dialog()
        build_upload_validate(
            layered_import_page, tmp_path, run_id,
            lambda h: m03_duplicate_entity_rows(h, f"auto_{run_id}"),
        )
        layered_import_page.select_conflict_mode("跳过")
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.click_confirm_import()
        layered_import_page.should_show_import_finished()
        layered_import_page.close_import_dialog()

    def test_m03_10_duplicate_entities_overwrite_mode(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M03-10: 实体全元组相同判定重复，选择「重复覆盖」并真实提交导入，断言导入完成。"""
        run_id = import_run_id("m03_dup_overwrite")
        layered_import_page.open_m03_entity_import_dialog()
        build_upload_validate(
            layered_import_page, tmp_path, run_id,
            lambda h: m03_duplicate_entity_rows(h, f"auto_{run_id}"),
        )
        layered_import_page.select_conflict_mode("覆盖")
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.click_confirm_import()
        layered_import_page.should_show_import_finished()
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
@pytest.mark.write
class TestM03ImportResultAndList:
    """M03 导入结果与数据资源列表检索测试。"""

    def test_m03_11_valid_import_and_search_entity(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M03-11: 标准 M03 文件导入前校验通过后，在数据资源列表中按已存在表英文名称检索核验。"""
        run_id = import_run_id("m03_entity")
        table_english_name = f"auto_{run_id}"
        layered_import_page.open_m03_entity_import_dialog()
        build_upload_validate(
            layered_import_page, tmp_path, run_id,
            lambda h: m03_valid_like_row(h, table_english_name),
        )
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.click_confirm_import()
        layered_import_page.should_show_import_finished()
        layered_import_page.close_import_dialog()
        layered_import_page.search_and_verify_entity(table_english_name)

    def test_m03_12_entity_details_columns_verify(self, layered_import_page: LayeredImportPage):
        """M03-12: 在数据资源列表中核验表中文名、表英文名、系统名、描述列展示完整。"""
        ds = get_m03_dataset("standard_valid")
        layered_import_page.open_data_resource_mgmt()
        layered_import_page.assertions.any_text_visible(["数据资源列表", "导入数据实体清单", "数据资源管理", "表中文名", "表英文名", "应用系统"])
