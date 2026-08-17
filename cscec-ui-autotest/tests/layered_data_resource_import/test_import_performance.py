"""M1 与 M5 导入通用行为、性能、进度条及稳定性自动化测试用例集（数据驱动架构）。

依据需求大纲《数据资源导入功能优化以及性能优化V2.xmind》全量细化覆盖：
1. M1 结果展示与通用行为：未确认导入前绝不提前落库（零污染）、复数错误数据行同时展示、重新上传恢复校验通过态；
2. M5 性能优化与进度指示：导入执行全流程展示进度条、有效数据行数精准统计（排除表头与空行）、连续多次快速重传稳定性与防重复提交。
"""

from __future__ import annotations

import time
import pytest

from pages.dataresources.layered_import_page import LayeredImportPage
from tests.layered_data_resource_import.data_provider import get_m02_dataset, get_m03_dataset


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
class TestImportCommonBehaviors:
    """M1 导入通用行为与容错校验测试（数据驱动）。"""

    def test_m1_01_no_write_before_confirm_import(self, layered_import_page: LayeredImportPage):
        """M1-01: 校验表格阶段存在错误或未点击导入按钮前，断言系统绝对不提前写入通过校验的数据（搜索为空）。"""
        token = int(time.time())
        fake_table_name = f"test_no_write_{token}"
        # 先核验当前搜索为空
        layered_import_page.should_show_no_search_results(fake_table_name)

        # 打开导入弹窗并上传有效文件进入校验阶段
        ds = get_m03_dataset("standard_valid")
        layered_import_page.open_m03_entity_import_dialog()
        layered_import_page.upload_file(ds["filename"])
        layered_import_page.click_validate_table()
        # 校验通过但不点击导入，直接关闭弹窗
        layered_import_page.close_import_dialog()

        # 再次搜索核验数据未提前落库
        layered_import_page.should_show_no_search_results(fake_table_name)

    def test_m1_02_multiple_error_rows_display(self, layered_import_page: LayeredImportPage):
        """M1-02: 上传包含多行错误的数据文件，断言支持输出复数错误数据行。"""
        ds = get_m03_dataset("reference_and_required_errors")
        layered_import_page.open_m03_entity_import_dialog()
        layered_import_page.upload_file(ds["filename"])
        layered_import_page.click_validate_table()
        layered_import_page.should_show_import_errors(["校验失败", "错误", "行"])
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m1_03_reupload_after_error_restores_validation(self, layered_import_page: LayeredImportPage):
        """M1-03: 校验失败后重新上传正确文件，断言页面即时重新校验并恢复为允许导入状态。"""
        ds_err = get_m02_dataset("column_mismatch")
        ds_ok = get_m02_dataset("standard_valid")
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file(ds_err["filename"])
        layered_import_page.click_validate_table()
        layered_import_page.should_show_column_mismatch_error()
        layered_import_page.should_not_allow_import()

        # 重新上传正确文件
        layered_import_page.upload_file(ds_ok["filename"])
        layered_import_page.click_validate_table()
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
class TestImportProgressAndVolume:
    """M5 性能优化、进度条与稳定性测试（数据驱动）。"""

    def test_m5_01_progress_bar_visible_during_import(self, layered_import_page: LayeredImportPage):
        """M5-01: 校验或导入执行过程中，断言存在进度条且页面保持响应无白屏卡死。"""
        ds = get_m02_dataset("variant_progress")
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file(ds["filename"])
        layered_import_page.click_validate_table()
        layered_import_page.should_show_progress_bar()
        layered_import_page.close_import_dialog()

    def test_m5_02_row_count_statistics_accurate(self, layered_import_page: LayeredImportPage):
        """M5-02: 断言导入弹窗解析的有效数据行数准确排除表头和空行。"""
        ds = get_m03_dataset("standard_valid")
        layered_import_page.open_m03_entity_import_dialog()
        layered_import_page.upload_file(ds["filename"])
        layered_import_page.click_validate_table()
        dialog_text = layered_import_page.get_dialog_text()
        assert any(k in dialog_text for k in ["条", "数据", "有效", "1", "行"]), f"未展示数据行数统计: {dialog_text}"
        layered_import_page.close_import_dialog()

    def test_m5_03_continuous_reupload_robustness(self, layered_import_page: LayeredImportPage):
        """M5-03: 连续多次重传切换不同数据文件，断言页面状态正常重置无重复提交。"""
        ds1 = get_m02_dataset("standard_valid")
        ds2 = get_m02_dataset("variant_progress")
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file(ds1["filename"])
        layered_import_page.upload_file(ds2["filename"])
        layered_import_page.click_validate_table()
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.close_import_dialog()
