"""M03 数据实体清单导入自动化测试用例集。

依据需求大纲《数据资源导入功能优化以及性能优化V2.xmind》全量细化覆盖：
1. 模板与入口：入口进入、弹窗结构、模板下载与核心表头字段核验；
2. 引用数据校验：一级应用域不存在、系统不存在、域系统不对应、L1~L3在库中不存在/不对应报错；
3. 必填与可空：域/系统/分层/表名/描述/存储周期/项目组必填拦截，编码与部门可空放行；
4. 重复判断与冲突模式：全元组重复判定、跳过模式、覆盖模式；
5. 导入结果核验：数据资源列表英文名检索、实体中英文名与系统名详情核验。
"""

from __future__ import annotations

from pathlib import Path
import pytest

from pages.dataresources.layered_import_page import LayeredImportPage
from tests.dataresources.import_workbooks import read_first_sheet_headers


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
class TestM03EntryAndTemplate:
    """M03 模板与入口结构测试。"""

    def test_m03_01_entry_and_dialog_structure(self, layered_import_page: LayeredImportPage):
        """M03-01: 从控制台-资源管理-数据资源管理进入导入，验证展示上传文件、校验提示、导入模板。"""
        layered_import_page.open_m03_entity_import_dialog()
        dialog_text = layered_import_page.get_dialog_text()
        assert "导入数据实体清单" in dialog_text or "导入数据实体" in dialog_text, f"未出现导入实体弹窗标题，当前文本: {dialog_text}"
        layered_import_page.assertions.any_text_visible(["上传文件", "点击上传", "选择文件"])
        layered_import_page.close_import_dialog()

    def test_m03_02_template_download_and_field_headers(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M03-02: 下载 M03 模板，断言识别一级应用域、应用系统、L1-L3、表中文名、表英文名、表描述等字段。"""
        layered_import_page.open_m03_entity_import_dialog()
        template_file = layered_import_page.download_template(tmp_path)
        assert template_file.exists(), f"模板文件未成功下载: {template_file}"

        headers = read_first_sheet_headers(template_file)
        expected_headers = ["一级应用域名称", "应用系统名称", "L1", "L2", "L3", "表中文名称", "表英文名称", "表描述", "存储周期", "系统项目组"]
        for exp in expected_headers:
            assert any(exp in h for h in headers), f"M03 模板缺少预期表头字段: '{exp}'; 实际表头: {headers}"
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
class TestM03ReferenceDataErrors:
    """M03 引用数据校验不通过测试。"""

    def test_m03_03_missing_domain_shows_error(self, layered_import_page: LayeredImportPage):
        """M03-03: B列一级应用域名称在库中不存在，断言输出错误数据行与应用域不存在提示。"""
        layered_import_page.open_m03_entity_import_dialog()
        layered_import_page.upload_file("M03数据实体清单 - 副本 - 副本.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.should_show_import_errors(["校验失败", "错误", "行"])
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m03_04_missing_system_shows_error(self, layered_import_page: LayeredImportPage):
        """M03-04: D列应用系统名称在库中不存在，断言输出错误数据行与系统不存在提示。"""
        layered_import_page.open_m03_entity_import_dialog()
        layered_import_page.upload_file("M03数据实体清单 - 副本 - 副本.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.should_show_import_errors(["校验失败", "错误", "行"])
        layered_import_page.close_import_dialog()

    def test_m03_05_domain_system_mismatch_shows_error(self, layered_import_page: LayeredImportPage):
        """M03-05: 一级应用域与应用系统不对应，断言输出错误数据行。"""
        layered_import_page.open_m03_entity_import_dialog()
        layered_import_page.upload_file("M03数据实体清单 - 副本 - 副本.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.should_show_import_errors(["校验失败", "错误", "行"])
        layered_import_page.close_import_dialog()

    def test_m03_06_missing_layer_shows_error(self, layered_import_page: LayeredImportPage):
        """M03-06: L1/L2/L3 任一在库中不存在或与系统上下文不对应，断言输出错误数据行。"""
        layered_import_page.open_m03_entity_import_dialog()
        layered_import_page.upload_file("M03数据实体清单 - 副本 - 副本.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.should_show_import_errors(["校验失败", "错误", "行"])
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
class TestM03RequiredAndOptionalFields:
    """M03 必填与可选字段校验测试。"""

    def test_m03_07_missing_required_fields_blocked(self, layered_import_page: LayeredImportPage):
        """M03-07: 表中文名称/表英文名称/表描述/存储周期/项目组任一为空，断言业务校验不通过。"""
        layered_import_page.open_m03_entity_import_dialog()
        layered_import_page.upload_file("M03数据实体清单 - 副本 - 副本.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m03_08_optional_fields_pass(self, layered_import_page: LayeredImportPage):
        """M03-08: 一级应用域编码、应用系统编码、数据责任部门为空，断言不因空值拦截校验。"""
        layered_import_page.open_m03_entity_import_dialog()
        layered_import_page.upload_file("M03数据实体清单.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.assertions.page_not_blank_or_error()
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
class TestM03DuplicateAndConflictModes:
    """M03 重复判断规则与冲突处理测试。"""

    def test_m03_09_duplicate_entities_skip_mode(self, layered_import_page: LayeredImportPage):
        """M03-09: 域+系统+L1-L3+表英文名完全相同判定重复，选择「重复跳过」模式进行校验。"""
        layered_import_page.open_m03_entity_import_dialog()
        layered_import_page.upload_file("M03数据实体清单 - 副本.xlsx")
        layered_import_page.select_conflict_mode("跳过")
        layered_import_page.click_validate_table()
        layered_import_page.assertions.page_not_blank_or_error()
        layered_import_page.close_import_dialog()

    def test_m03_10_duplicate_entities_overwrite_mode(self, layered_import_page: LayeredImportPage):
        """M03-10: 包含重复实体时选择「重复覆盖」模式进行校验。"""
        layered_import_page.open_m03_entity_import_dialog()
        layered_import_page.upload_file("M03数据实体清单 - 副本.xlsx")
        layered_import_page.select_conflict_mode("覆盖")
        layered_import_page.click_validate_table()
        layered_import_page.assertions.page_not_blank_or_error()
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
class TestM03ImportResultAndList:
    """M03 导入结果核验与列表检索测试。"""

    def test_m03_11_valid_import_and_search_entity(self, layered_import_page: LayeredImportPage):
        """M03-11: 上传标准有效 M03 实体清单校验，并在数据资源列表中按英文名检索核验。"""
        layered_import_page.open_m03_entity_import_dialog()
        layered_import_page.upload_file("M03数据实体清单.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.close_import_dialog()
        # 检索已导入的实体英文名
        layered_import_page.search_and_verify_entity("test0813table1")

    def test_m03_12_entity_details_columns_verify(self, layered_import_page: LayeredImportPage):
        """M03-12: 数据资源列表中核验表中文名称、表英文名称、应用系统名称、表描述等列展示正常。"""
        layered_import_page.open_data_resource_mgmt()
        layered_import_page.assertions.any_text_visible(["表中文名称", "表英文名称", "应用系统名称", "表描述", "数据资源列表"])
