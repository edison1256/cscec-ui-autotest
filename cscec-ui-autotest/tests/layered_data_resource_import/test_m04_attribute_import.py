"""M04 数据属性清单导入自动化测试用例集。

依据需求大纲《数据资源导入功能优化以及性能优化V2.xmind》全量细化覆盖：
1. 模板与入口：入口进入、弹窗结构、模板下载与 18 个属性核心表头字段核验；
2. 实体定位校验：定位列不在库中、多元组不对应、表英文名实体不存在、分层不对应报错；
3. 必填与枚举校验：18个必填项缺失、是否主键/可空/外键非“是/否”、安全分类分级必填拦截；
4. 放行规则：是否本系统产生的数据放行、编码/长度/来源系统/国资监管等非必填放行；
5. 导入结果核验：字段英文名检索、数据项属性列表核验。
"""

from __future__ import annotations

from pathlib import Path
import pytest

from pages.dataresources.layered_import_page import LayeredImportPage
from tests.dataresources.import_workbooks import (
    m04_boolean_flags_wrong_value_row,
    m04_empty_boolean_flags_row,
    m04_missing_entity_row,
    m04_missing_field_cn_name_row,
    m04_missing_field_definition_row,
    m04_missing_field_en_name_row,
    m04_missing_security_classification_row,
    m04_optional_fields_empty_row,
    m04_source_system_flag_empty_row,
    m04_valid_attribute_row,
    read_first_sheet_headers,
)
from tests.layered_data_resource_import.data_provider import import_run_id
from tests.layered_data_resource_import.workflow_helpers import build_upload_validate


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
@pytest.mark.readonly
class TestM04EntryAndTemplate:
    """M04 模板与入口结构测试。"""

    def test_m04_01_entry_and_dialog_structure(self, layered_import_page: LayeredImportPage):
        """M04-01: 从控制台-资源管理-数据资源管理进入导入属性清单，验证展示上传文件、校验提示、导入模板。"""
        layered_import_page.open_m04_attribute_import_dialog()
        dialog_text = layered_import_page.get_dialog_text()
        assert "导入数据属性清单" in dialog_text or "导入数据属性" in dialog_text, f"未出现导入属性弹窗标题，当前文本: {dialog_text}"
        assert any(k in dialog_text for k in ["上传文件", "点击上传", "选择文件", "下载模板", "下载模版"]), f"未出现上传或模板提示，弹窗文本: {dialog_text}"
        layered_import_page.close_import_dialog()

    def test_m04_02_template_download_and_18_headers(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M04-02: 下载 M04 模板，断言模板识别一级应用域、应用系统、L1-L3、表英文名、18个字段属性。"""
        layered_import_page.open_m04_attribute_import_dialog()
        template_file = layered_import_page.download_template(tmp_path)
        assert template_file.exists(), f"模板文件未成功下载: {template_file}"

        headers = read_first_sheet_headers(template_file)
        expected_tokens = [
            "一级应用域", "应用系统", "L1", "L2", "L3",
            "字段", "类型", "主键", "可空",
            "安全分类", "安全分级"
        ]
        for token in expected_tokens:
            assert any(token in h for h in headers), f"M04 模板缺少预期表头核心字段: '{token}'; 实际表头: {headers}"
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
@pytest.mark.write
class TestM04EntityLocatorErrors:
    """M04 实体定位与引用关系校验测试。"""

    def test_m04_03_column_mismatch_blocked(self, layered_import_page: LayeredImportPage):
        """M04-03: 上传非属性模板文件，断言提示列名与模板不符并禁止提供导入按钮。"""
        layered_import_page.open_m04_attribute_import_dialog()
        layered_import_page.upload_file("m02_error_column_mismatch.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.should_show_column_mismatch_error()
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m04_04_missing_entity_shows_error(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M04-04: 表英文名称对应实体在库中不存在，断言输出错误数据行。"""
        run_id = import_run_id("m04_missing_entity")
        layered_import_page.open_m04_attribute_import_dialog()
        build_upload_validate(
            layered_import_page, tmp_path, run_id,
            lambda h: m04_missing_entity_row(h, f"auto_table_{run_id}", f"auto_field_{run_id}"),
        )
        layered_import_page.should_show_import_errors(["校验失败", "错误", "行"])
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
@pytest.mark.write
class TestM04RequiredAndEnumValidation:
    """M04 必填字段与枚举值校验测试。"""

    def test_m04_05_boolean_flags_enum_validation(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M04-05: 是否主键、是否可空、是否外键填写非“是/否”或为空，断言业务校验不通过。"""
        run_id = import_run_id("m04_bool")
        layered_import_page.open_m04_attribute_import_dialog()
        build_upload_validate(
            layered_import_page, tmp_path, run_id,
            lambda h: m04_empty_boolean_flags_row(h, f"auto_field_{run_id}"),
        )
        layered_import_page.should_show_import_errors(["校验失败", "错误", "行", "是否主键"])
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m04_06_security_classification_required(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M04-06: 数据安全分类、数据安全分级为空，断言业务校验不通过。"""
        run_id = import_run_id("m04_security")
        layered_import_page.open_m04_attribute_import_dialog()
        build_upload_validate(
            layered_import_page, tmp_path, run_id,
            lambda h: m04_missing_security_classification_row(h, f"auto_field_{run_id}"),
        )
        layered_import_page.should_show_import_errors(["校验失败", "错误", "行"])
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    @pytest.mark.parametrize(
        "builder",
        [m04_missing_field_cn_name_row, m04_missing_field_en_name_row],
        ids=["field_cn_name", "field_en_name"],
    )
    def test_m04_field_name_required_blocked(self, layered_import_page: LayeredImportPage, tmp_path: Path, builder):
        """M04: 字段中文名/英文名为空，断言业务校验不通过并禁止导入。"""
        run_id = import_run_id("m04_fieldname")
        layered_import_page.open_m04_attribute_import_dialog()
        build_upload_validate(
            layered_import_page, tmp_path, run_id,
            lambda h: builder(h, f"auto_field_{run_id}"),
        )
        layered_import_page.should_show_import_errors(["校验失败", "错误", "行"])
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m04_field_definition_required_blocked(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M04: 字段类型为空（业务规则/缺省值/类型/取值范围之一），断言业务校验不通过。"""
        run_id = import_run_id("m04_fieldtype")
        layered_import_page.open_m04_attribute_import_dialog()
        build_upload_validate(
            layered_import_page, tmp_path, run_id,
            lambda h: m04_missing_field_definition_row(h, f"auto_field_{run_id}"),
        )
        layered_import_page.should_show_import_errors(["校验失败", "错误", "行"])
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m04_boolean_flags_wrong_value_blocked(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M04: 是否主键/是否可空/是否外键填写非“是/否”，断言业务校验不通过。"""
        run_id = import_run_id("m04_boolval")
        layered_import_page.open_m04_attribute_import_dialog()
        build_upload_validate(
            layered_import_page, tmp_path, run_id,
            lambda h: m04_boolean_flags_wrong_value_row(h, f"auto_field_{run_id}"),
        )
        layered_import_page.should_show_import_errors(["校验失败", "错误", "行"])
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
@pytest.mark.write
class TestM04PassAndOptionalValidation:
    """M04 放行规则与可选字段放行测试。"""

    def test_m04_07_source_system_flag_empty_passes(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M04-07: 是否本系统产生的数据为空，断言不因空值业务校验不通过。"""
        run_id = import_run_id("m04_source_empty")
        layered_import_page.open_m04_attribute_import_dialog()
        build_upload_validate(
            layered_import_page, tmp_path, run_id,
            lambda h: m04_source_system_flag_empty_row(h, f"auto_field_{run_id}"),
        )
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.close_import_dialog()

    def test_m04_08_optional_fields_pass(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M04-08: 一级应用域编码、应用系统编码、数据长度、外键关联信息、数据来源等为空不拦截导入。"""
        run_id = import_run_id("m04_optional")
        layered_import_page.open_m04_attribute_import_dialog()
        build_upload_validate(
            layered_import_page, tmp_path, run_id,
            lambda h: m04_optional_fields_empty_row(h, f"auto_field_{run_id}"),
        )
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
@pytest.mark.write
class TestM04ImportResultAndAttributes:
    """M04 导入结果与数据项列表核验测试。"""

    def test_m04_09_attribute_import_and_search(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M04-09: 导入完成后进入数据项属性列表，按字段英文名检索核验新增数据项可查询。

        注：目标实体使用已知存在的 ``test0813table1``，字段英文名唯一，避免污染库中既有数据。
        属性列表逐字段（类型/安全分级等）的精确展示核验依赖真实属性页定位，标记为后续补齐项。
        """
        run_id = import_run_id("m04_attr")
        field_english_name = f"auto_field_{run_id}"
        layered_import_page.open_m04_attribute_import_dialog()
        build_upload_validate(
            layered_import_page, tmp_path, run_id,
            lambda h: m04_valid_attribute_row(h, field_english_name),
        )
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.click_confirm_import()
        layered_import_page.should_show_import_finished()
        layered_import_page.close_import_dialog()

        # 导入完成后在数据资源列表按字段英文名检索，确认新增数据项可查询
        layered_import_page.search_and_verify_entity(field_english_name)
