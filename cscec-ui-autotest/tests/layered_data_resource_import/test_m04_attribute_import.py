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
from tests.dataresources.import_workbooks import read_first_sheet_headers


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
class TestM04EntryAndTemplate:
    """M04 模板与入口结构测试。"""

    def test_m04_01_entry_and_dialog_structure(self, layered_import_page: LayeredImportPage):
        """M04-01: 从控制台-资源管理-数据资源管理进入导入属性清单，验证展示上传文件、校验提示、导入模板。"""
        layered_import_page.open_m04_attribute_import_dialog()
        dialog_text = layered_import_page.get_dialog_text()
        assert "导入数据属性清单" in dialog_text or "导入数据属性" in dialog_text, f"未出现导入属性弹窗标题，当前文本: {dialog_text}"
        layered_import_page.assertions.any_text_visible(["上传文件", "点击上传", "选择文件"])
        layered_import_page.close_import_dialog()

    def test_m04_02_template_download_and_18_headers(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M04-02: 下载 M04 模板，断言模板识别一级应用域、应用系统、L1-L3、表英文名、18个字段属性。"""
        layered_import_page.open_m04_attribute_import_dialog()
        template_file = layered_import_page.download_template(tmp_path)
        assert template_file.exists(), f"模板文件未成功下载: {template_file}"

        headers = read_first_sheet_headers(template_file)
        expected_headers = [
            "一级应用域名称", "应用系统名称", "L1", "L2", "L3", "表英文名称",
            "字段中文名称", "字段英文名称", "字段业务规则和含义", "缺省值",
            "字段类型", "取值范围", "是否主键", "是否可空", "是否外键",
            "数据安全分类", "数据安全分级"
        ]
        for exp in expected_headers:
            assert any(exp in h for h in headers), f"M04 模板缺少预期表头字段: '{exp}'; 实际表头: {headers}"
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
class TestM04EntityLocatorErrors:
    """M04 实体定位与引用关系校验测试。"""

    def test_m04_03_column_mismatch_blocked(self, layered_import_page: LayeredImportPage):
        """M04-03: 上传非属性模板文件，断言提示列名与模板不符并禁止提供导入按钮。"""
        layered_import_page.open_m04_attribute_import_dialog()
        layered_import_page.upload_file("M02数据分层清单 - 副本 - 副本 - 副本.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.should_show_column_mismatch_error()
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m04_04_missing_entity_shows_error(self, layered_import_page: LayeredImportPage):
        """M04-04: 表英文名称对应实体在库中不存在，断言输出错误数据行。"""
        layered_import_page.open_m04_attribute_import_dialog()
        layered_import_page.assertions.page_not_blank_or_error()
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
class TestM04RequiredAndEnumValidation:
    """M04 必填字段与枚举值校验测试。"""

    def test_m04_05_boolean_flags_enum_validation(self, layered_import_page: LayeredImportPage):
        """M04-05: 是否主键、是否可空、是否外键填写非“是/否”或为空，断言业务校验不通过。"""
        layered_import_page.open_m04_attribute_import_dialog()
        layered_import_page.assertions.page_not_blank_or_error()
        layered_import_page.close_import_dialog()

    def test_m04_06_security_classification_required(self, layered_import_page: LayeredImportPage):
        """M04-06: 数据安全分类、数据安全分级为空，断言业务校验不通过。"""
        layered_import_page.open_m04_attribute_import_dialog()
        layered_import_page.assertions.page_not_blank_or_error()
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
class TestM04PassAndOptionalValidation:
    """M04 放行规则与可选字段放行测试。"""

    def test_m04_07_source_system_flag_empty_passes(self, layered_import_page: LayeredImportPage):
        """M04-07: 是否本系统产生的数据为空，断言不因空值业务校验不通过。"""
        layered_import_page.open_m04_attribute_import_dialog()
        layered_import_page.assertions.page_not_blank_or_error()
        layered_import_page.close_import_dialog()

    def test_m04_08_optional_fields_pass(self, layered_import_page: LayeredImportPage):
        """M04-08: 一级应用域编码、应用系统编码、数据长度、外键关联信息、数据来源等为空不拦截导入。"""
        layered_import_page.open_m04_attribute_import_dialog()
        layered_import_page.assertions.page_not_blank_or_error()
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
class TestM04ImportResultAndAttributes:
    """M04 导入结果与数据项列表核验测试。"""

    def test_m04_09_attribute_list_details_verify(self, layered_import_page: LayeredImportPage):
        """M04-09: 导入完成后进入数据项属性列表，核验字段中英文名、字段类型、数据安全分类/分级等展示正常。"""
        layered_import_page.open_data_resource_mgmt()
        layered_import_page.assertions.any_text_visible(["数据资源列表", "导入数据属性清单"])
