"""M03/M04 data resource import dialog contract tests."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from tests.dataresources.import_workbooks import (
    create_workbook_from_headers,
    m03_app_domain_system_mismatch_row,
    m03_missing_app_domain_row,
    m03_missing_app_system_row,
    m03_missing_layer_row,
    m03_missing_required_field_row,
    m03_multiple_error_rows,
    m03_valid_pre_import_row,
    m04_empty_boolean_flags_row,
    m04_invalid_attribute_row,
    m04_locator_mismatch_row,
    m04_missing_entity_row,
    m04_missing_locator_row,
    m04_missing_required_field_row,
    m04_optional_fields_empty_row,
    m04_source_system_flag_empty_row,
    m04_source_system_flag_unrestricted_row,
    read_first_sheet_headers,
)


IMPORT_CONTRACTS = [
    pytest.param(
        "M03",
        ["一级应用域名称", "表英文名称"],
        id="m03",
    ),
    pytest.param(
        "M04",
        ["一级应用域名称", "表英文名", "字段英文名"],
        id="m04",
    ),
]


@pytest.mark.dataresources
@pytest.mark.regression
@pytest.mark.readonly
class TestM03M04ImportContracts:
    """UI-CAND-0002, UI-CAND-0003, UI-CAND-0069."""

    @pytest.mark.parametrize(("import_type", "required_headers"), IMPORT_CONTRACTS)
    def test_import_dialog_and_template_download_are_available(
        self,
        data_resources,
        tmp_path: Path,
        import_type: str,
        required_headers: list[str],
    ):
        data_resources.open_import_dialog(import_type)
        data_resources.should_show_import_dialog(import_type)
        data_resources.should_have_import_upload()

        template_path = data_resources.download_import_template(tmp_path, import_type)
        headers = read_first_sheet_headers(template_path)

        for header in required_headers:
            assert header in headers

        data_resources.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.regression
@pytest.mark.write
class TestM03M04ImportBusinessErrors:
    """UI-CAND-0030, UI-CAND-0048, and UI-CAND-0049."""

    def test_m03_missing_app_domain_shows_error_row(self, data_resources, tmp_path: Path):
        token = int(time.time())
        table_english_name = f"auto_m03_missing_domain_{token}"

        data_resources.open_import_dialog("M03")
        template_path = data_resources.download_import_template(tmp_path, "M03")
        headers = read_first_sheet_headers(template_path)
        import_file = create_workbook_from_headers(
            tmp_path,
            f"M03_missing_app_domain_{token}.xlsx",
            headers,
            m03_missing_app_domain_row(headers, table_english_name),
        )

        data_resources.upload_import_file(str(import_file))
        data_resources.click_validate_table()
        data_resources.should_show_import_errors(["校验失败", "错误行号", "第 2 行", "一级应用域不存在"])
        data_resources.should_not_allow_import()
        data_resources.close_import_dialog()

    def test_m04_invalid_attribute_values_show_error_row(self, data_resources, tmp_path: Path):
        token = int(time.time())
        table_english_name = f"auto_m04_invalid_attr_{token}"
        field_english_name = f"auto_field_{token}"

        data_resources.open_import_dialog("M04")
        template_path = data_resources.download_import_template(tmp_path, "M04")
        headers = read_first_sheet_headers(template_path)
        import_file = create_workbook_from_headers(
            tmp_path,
            f"M04_invalid_attribute_{token}.xlsx",
            headers,
            m04_invalid_attribute_row(headers, table_english_name, field_english_name),
        )

        data_resources.upload_import_file(str(import_file))
        data_resources.click_validate_table()
        data_resources.should_show_import_errors(["校验失败", "错误行号", "第 2 行"])
        data_resources.should_show_import_errors(["一级应用域不存在", "不正确"])
        data_resources.should_not_allow_import()
        data_resources.close_import_dialog()

    def test_m04_missing_required_field_shows_error_row(self, data_resources, tmp_path: Path):
        token = int(time.time())
        table_english_name = f"auto_m04_missing_required_{token}"
        field_english_name = f"auto_required_{token}"

        data_resources.open_import_dialog("M04")
        template_path = data_resources.download_import_template(tmp_path, "M04")
        headers = read_first_sheet_headers(template_path)
        import_file = create_workbook_from_headers(
            tmp_path,
            f"M04_missing_required_{token}.xlsx",
            headers,
            m04_missing_required_field_row(headers, table_english_name, field_english_name),
        )

        data_resources.upload_import_file(str(import_file))
        data_resources.click_validate_table()
        data_resources.should_show_import_errors(["校验失败", "错误行号", "第 2 行", "一级应用域"])
        data_resources.should_not_allow_import()
        data_resources.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.regression
@pytest.mark.write
class TestM03M04ImportA1BusinessErrors:
    """UI-CAND-0031, UI-CAND-0032, UI-CAND-0033, UI-CAND-0034, UI-CAND-0045, UI-CAND-0046."""

    def test_m03_missing_app_system_shows_error_row(self, data_resources, tmp_path: Path):
        token = int(time.time())
        table_english_name = f"auto_m03_missing_system_{token}"

        data_resources.open_import_dialog("M03")
        template_path = data_resources.download_import_template(tmp_path, "M03")
        headers = read_first_sheet_headers(template_path)
        import_file = create_workbook_from_headers(
            tmp_path,
            f"M03_missing_app_system_{token}.xlsx",
            headers,
            m03_missing_app_system_row(headers, table_english_name),
        )

        data_resources.upload_import_file(str(import_file))
        data_resources.click_validate_table()
        data_resources.should_show_import_errors(["校验失败", "错误行号", "第 2 行", "应用系统"])
        data_resources.should_not_allow_import()
        data_resources.close_import_dialog()

    def test_m03_app_domain_system_mismatch_shows_error_row(self, data_resources, tmp_path: Path):
        token = int(time.time())
        table_english_name = f"auto_m03_domain_system_mismatch_{token}"

        data_resources.open_import_dialog("M03")
        template_path = data_resources.download_import_template(tmp_path, "M03")
        headers = read_first_sheet_headers(template_path)
        import_file = create_workbook_from_headers(
            tmp_path,
            f"M03_domain_system_mismatch_{token}.xlsx",
            headers,
            m03_app_domain_system_mismatch_row(headers, table_english_name),
        )

        data_resources.upload_import_file(str(import_file))
        data_resources.click_validate_table()
        data_resources.should_show_import_errors(["校验失败", "错误行号", "第 2 行", "应用系统"])
        data_resources.should_not_allow_import()
        data_resources.close_import_dialog()

    def test_m03_missing_layer_shows_error_row(self, data_resources, tmp_path: Path):
        token = int(time.time())
        table_english_name = f"auto_m03_missing_layer_{token}"

        data_resources.open_import_dialog("M03")
        template_path = data_resources.download_import_template(tmp_path, "M03")
        headers = read_first_sheet_headers(template_path)
        import_file = create_workbook_from_headers(
            tmp_path,
            f"M03_missing_layer_{token}.xlsx",
            headers,
            m03_missing_layer_row(headers, table_english_name),
        )

        data_resources.upload_import_file(str(import_file))
        data_resources.click_validate_table()
        data_resources.should_show_import_errors(["校验失败", "错误行号", "第 2 行", "L2"])
        data_resources.should_not_allow_import()
        data_resources.close_import_dialog()

    def test_m03_missing_required_field_shows_error_row(self, data_resources, tmp_path: Path):
        token = int(time.time())
        table_english_name = f"auto_m03_missing_required_{token}"

        data_resources.open_import_dialog("M03")
        template_path = data_resources.download_import_template(tmp_path, "M03")
        headers = read_first_sheet_headers(template_path)
        import_file = create_workbook_from_headers(
            tmp_path,
            f"M03_missing_required_{token}.xlsx",
            headers,
            m03_missing_required_field_row(headers, table_english_name),
        )

        data_resources.upload_import_file(str(import_file))
        data_resources.click_validate_table()
        data_resources.should_show_import_errors(["校验失败", "错误行号", "第 2 行", "表英文名"])
        data_resources.should_not_allow_import()
        data_resources.close_import_dialog()

    def test_m04_missing_locator_shows_error_row(self, data_resources, tmp_path: Path):
        token = int(time.time())
        table_english_name = f"auto_m04_missing_locator_{token}"
        field_english_name = f"auto_locator_{token}"

        data_resources.open_import_dialog("M04")
        template_path = data_resources.download_import_template(tmp_path, "M04")
        headers = read_first_sheet_headers(template_path)
        import_file = create_workbook_from_headers(
            tmp_path,
            f"M04_missing_locator_{token}.xlsx",
            headers,
            m04_missing_locator_row(headers, table_english_name, field_english_name),
        )

        data_resources.upload_import_file(str(import_file))
        data_resources.click_validate_table()
        data_resources.should_show_import_errors(["校验失败", "错误行号", "第 2 行", "L1"])
        data_resources.should_not_allow_import()
        data_resources.close_import_dialog()

    def test_m04_locator_mismatch_shows_error_row(self, data_resources, tmp_path: Path):
        token = int(time.time())
        table_english_name = f"auto_m04_locator_mismatch_{token}"
        field_english_name = f"auto_mismatch_{token}"

        data_resources.open_import_dialog("M04")
        template_path = data_resources.download_import_template(tmp_path, "M04")
        headers = read_first_sheet_headers(template_path)
        import_file = create_workbook_from_headers(
            tmp_path,
            f"M04_locator_mismatch_{token}.xlsx",
            headers,
            m04_locator_mismatch_row(headers, table_english_name, field_english_name),
        )

        data_resources.upload_import_file(str(import_file))
        data_resources.click_validate_table()
        data_resources.should_show_import_errors(["校验失败", "错误行号", "第 2 行", "应用系统"])
        data_resources.should_not_allow_import()
        data_resources.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.regression
@pytest.mark.write
class TestM03M04ImportA2BusinessErrors:
    """UI-CAND-0047 and UI-CAND-0050."""

    def test_m04_missing_entity_shows_error_row(self, data_resources, tmp_path: Path):
        token = int(time.time())
        table_english_name = f"auto_m04_missing_entity_{token}"
        field_english_name = f"auto_missing_entity_{token}"

        data_resources.open_import_dialog("M04")
        template_path = data_resources.download_import_template(tmp_path, "M04")
        headers = read_first_sheet_headers(template_path)
        import_file = create_workbook_from_headers(
            tmp_path,
            f"M04_missing_entity_{token}.xlsx",
            headers,
            m04_missing_entity_row(headers, table_english_name, field_english_name),
        )

        data_resources.upload_import_file(str(import_file))
        data_resources.click_validate_table()
        data_resources.should_show_import_errors(["校验失败", "错误行号", "第 2 行", "表在该应用系统的该分层下不存在"])
        data_resources.should_not_allow_import()
        data_resources.close_import_dialog()

    def test_m04_empty_boolean_flags_show_error_row(self, data_resources, tmp_path: Path):
        token = int(time.time())
        field_english_name = f"auto_empty_bool_{token}"

        data_resources.open_import_dialog("M04")
        template_path = data_resources.download_import_template(tmp_path, "M04")
        headers = read_first_sheet_headers(template_path)
        import_file = create_workbook_from_headers(
            tmp_path,
            f"M04_empty_boolean_flags_{token}.xlsx",
            headers,
            m04_empty_boolean_flags_row(headers, field_english_name),
        )

        data_resources.upload_import_file(str(import_file))
        data_resources.click_validate_table()
        data_resources.should_show_import_errors(["校验失败", "错误行号", "第 2 行", "是否主键"])
        data_resources.should_not_allow_import()
        data_resources.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.regression
@pytest.mark.write
class TestM03M04ImportA3PositiveContracts:
    """UI-CAND-0051, UI-CAND-0052, and UI-CAND-0053."""

    def test_m04_empty_source_system_flag_does_not_block_validation(self, data_resources, tmp_path: Path):
        token = int(time.time())
        field_english_name = f"auto_source_empty_{token}"

        data_resources.open_import_dialog("M04")
        template_path = data_resources.download_import_template(tmp_path, "M04")
        headers = read_first_sheet_headers(template_path)
        import_file = create_workbook_from_headers(
            tmp_path,
            f"M04_source_system_flag_empty_{token}.xlsx",
            headers,
            m04_source_system_flag_empty_row(headers, field_english_name),
        )

        data_resources.upload_import_file(str(import_file))
        data_resources.click_validate_table()
        data_resources.should_allow_import_after_validation()
        data_resources.close_import_dialog()

    # TODO(M04-009 转正): 本用例为受控监控项。后端放开「是否本系统产生的数据」的非 是/否 取值后，
    # 该用例预期会 XPASS（strict xfail 下 XPASS 会被判为失败）。届时移除下方 @pytest.mark.xfail 装饰器，
    # 使其转正为正式断言（验证非 是/否 取值不应拦截校验）。转正前请勿删除本注释。
    @pytest.mark.xfail(
        reason=(
            "后端尚未放开「是否本系统产生的数据」的非 是/否 取值（UAT 当前仍拦截）；"
            "后端修复后应 XPASS，需移除 @pytest.mark.xfail 转正为正式断言"
        ),
        strict=True,
    )
    def test_m04_non_yes_no_source_system_flag_does_not_block_validation(self, data_resources, tmp_path: Path):
        token = int(time.time())
        field_english_name = f"auto_source_any_{token}"

        data_resources.open_import_dialog("M04")
        template_path = data_resources.download_import_template(tmp_path, "M04")
        headers = read_first_sheet_headers(template_path)
        import_file = create_workbook_from_headers(
            tmp_path,
            f"M04_source_system_flag_unrestricted_{token}.xlsx",
            headers,
            m04_source_system_flag_unrestricted_row(headers, field_english_name),
        )

        data_resources.upload_import_file(str(import_file))
        data_resources.click_validate_table()
        data_resources.should_allow_import_after_validation()
        data_resources.close_import_dialog()

    def test_m04_optional_fields_empty_do_not_block_validation(self, data_resources, tmp_path: Path):
        token = int(time.time())
        field_english_name = f"auto_optional_empty_{token}"

        data_resources.open_import_dialog("M04")
        template_path = data_resources.download_import_template(tmp_path, "M04")
        headers = read_first_sheet_headers(template_path)
        import_file = create_workbook_from_headers(
            tmp_path,
            f"M04_optional_fields_empty_{token}.xlsx",
            headers,
            m04_optional_fields_empty_row(headers, field_english_name),
        )

        data_resources.upload_import_file(str(import_file))
        data_resources.click_validate_table()
        data_resources.should_allow_import_after_validation()
        data_resources.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.regression
@pytest.mark.write
class TestM03ImportA5PreImportContracts:
    """UI-CAND-0005 and UI-CAND-0009."""

    def test_m03_valid_xlsx_passes_validation_without_pre_import_write(
        self,
        data_resources,
        tmp_path: Path,
    ):
        token = int(time.time())
        table_english_name = f"auto_m03_pre_import_{token}"

        data_resources.open_import_dialog("M03")
        template_path = data_resources.download_import_template(tmp_path, "M03")
        headers = read_first_sheet_headers(template_path)
        import_file = create_workbook_from_headers(
            tmp_path,
            f"M03_pre_import_{token}.xlsx",
            headers,
            m03_valid_pre_import_row(headers, table_english_name),
        )

        data_resources.upload_import_file(str(import_file))
        data_resources.click_validate_table()
        # 校验通过、导入按钮可用，但绝不点击最终导入
        data_resources.should_allow_import_after_validation()
        data_resources.close_import_dialog()

        # 未点击导入 → 库中不应出现该实体
        data_resources.search_by_keyword(table_english_name)
        data_resources.should_show_no_search_results()


@pytest.mark.dataresources
@pytest.mark.regression
@pytest.mark.write
class TestM03ImportA6DialogState:
    """UI-CAND-0007 and UI-CAND-0008."""

    def test_m03_multiple_invalid_rows_show_multiple_error_lines(self, data_resources, tmp_path: Path):
        token = int(time.time())
        table_english_name = f"auto_m03_multi_error_{token}"

        data_resources.open_import_dialog("M03")
        template_path = data_resources.download_import_template(tmp_path, "M03")
        headers = read_first_sheet_headers(template_path)
        import_file = create_workbook_from_headers(
            tmp_path,
            f"M03_multiple_error_rows_{token}.xlsx",
            headers,
            m03_multiple_error_rows(headers, table_english_name),
        )

        data_resources.upload_import_file(str(import_file))
        data_resources.click_validate_table()
        data_resources.should_show_import_errors(["校验失败", "错误行号", "第 2 行", "第 3 行"])
        data_resources.should_not_allow_import()
        data_resources.close_import_dialog()

    def test_m03_reupload_valid_file_after_error_returns_to_passed_validation(self, data_resources, tmp_path: Path):
        token = int(time.time())
        invalid_table_english_name = f"auto_m03_reupload_bad_{token}"
        valid_table_english_name = f"auto_m03_reupload_ok_{token}"

        data_resources.search_by_keyword(valid_table_english_name)
        data_resources.should_show_no_search_results()

        data_resources.open_import_dialog("M03")
        template_path = data_resources.download_import_template(tmp_path, "M03")
        headers = read_first_sheet_headers(template_path)
        invalid_file = create_workbook_from_headers(
            tmp_path,
            f"M03_reupload_invalid_{token}.xlsx",
            headers,
            m03_missing_app_domain_row(headers, invalid_table_english_name),
        )
        valid_file = create_workbook_from_headers(
            tmp_path,
            f"M03_reupload_valid_{token}.xlsx",
            headers,
            m03_valid_pre_import_row(headers, valid_table_english_name),
        )

        data_resources.upload_import_file(str(invalid_file))
        data_resources.click_validate_table()
        data_resources.should_show_import_errors(["校验失败", "错误行号", "第 2 行"])
        data_resources.should_not_allow_import()

        data_resources.upload_import_file(str(valid_file))
        data_resources.click_validate_table()
        data_resources.should_allow_import_after_validation()
        data_resources.close_import_dialog()

        data_resources.search_by_keyword(valid_table_english_name)
        data_resources.should_show_no_search_results()
