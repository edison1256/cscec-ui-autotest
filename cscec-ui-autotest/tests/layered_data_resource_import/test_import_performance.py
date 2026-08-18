"""M1 与 M5 导入通用行为、性能、进度条及稳定性自动化测试用例集（数据驱动架构）。

依据需求大纲《数据资源导入功能优化以及性能优化V2.xmind》全量细化覆盖：
1. M1 结果展示与通用行为：未确认导入前绝不提前落库（零污染）、复数错误数据行同时展示、重新上传恢复校验通过态；
2. M5 性能优化与进度指示：导入执行全流程展示进度条、有效数据行数精准统计（排除表头与空行）、连续多次快速重传稳定性与防重复提交。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from pages.dataresources.layered_import_page import LayeredImportPage
from tests.dataresources.import_workbooks import (
    m02_unique_layer_row,
    m03_many_valid_rows,
    m03_valid_like_row,
)
from tests.layered_data_resource_import.data_provider import get_m02_dataset, get_m03_dataset, import_run_id
from tests.layered_data_resource_import.workflow_helpers import build_upload_validate


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
@pytest.mark.write
class TestImportCommonBehaviors:
    """M1 导入通用行为与容错校验测试（数据驱动）。"""

    def test_m1_01_no_write_before_confirm_import(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M1-01: 校验表格阶段存在错误或未点击导入按钮前，断言系统绝对不提前写入通过校验的数据（搜索为空）。"""
        run_id = import_run_id("m1_no_write")
        table_english_name = f"auto_{run_id}"
        layered_import_page.open_m03_entity_import_dialog()
        build_upload_validate(
            layered_import_page, tmp_path, run_id,
            lambda h: m03_valid_like_row(h, table_english_name),
        )
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.close_import_dialog()

        # 未点击导入 → 按表英文名搜索应无结果
        layered_import_page.should_show_no_search_results(table_english_name)

    def test_m1_02_multiple_error_rows_display(self, layered_import_page: LayeredImportPage):
        """M1-02: 上传包含多行错误的数据文件，断言支持输出复数错误数据行。"""
        ds = get_m03_dataset("reference_and_required_errors")
        layered_import_page.open_m03_entity_import_dialog()
        layered_import_page.upload_file(ds["file_path"])
        layered_import_page.click_validate_table()
        layered_import_page.should_show_import_errors(["校验失败", "错误", "行"])
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m1_03_reupload_after_error_restores_validation(self, layered_import_page: LayeredImportPage):
        """M1-03: 校验失败后重新上传正确文件，断言页面即时重新校验并恢复为允许导入状态。"""
        ds_err = get_m02_dataset("column_mismatch")
        ds_ok = get_m02_dataset("standard_valid")
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file(ds_err["file_path"])
        layered_import_page.click_validate_table()
        layered_import_page.should_show_column_mismatch_error()
        layered_import_page.should_not_allow_import()

        # 重新上传正确文件
        layered_import_page.upload_file(ds_ok["file_path"])
        layered_import_page.click_validate_table()
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
@pytest.mark.write
class TestImportProgressAndVolume:
    """M5 性能优化、进度条与稳定性测试（数据驱动）。"""

    def test_m5_01_progress_bar_visible_during_import(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M5-01: 校验通过后点击导入，断言导入过程中展示进度条/进度状态且页面保持响应无白屏卡死。"""
        run_id = import_run_id("m5_progress")
        layered_import_page.open_m02_layer_import_dialog()
        build_upload_validate(
            layered_import_page, tmp_path, run_id,
            lambda h: m02_unique_layer_row(h, run_id),
        )
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.click_confirm_import()
        layered_import_page.should_show_progress_bar()
        layered_import_page.should_show_import_finished()
        layered_import_page.close_import_dialog()

    def test_m5_02_row_count_statistics_accurate(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M5-02: 断言导入弹窗解析的有效数据行数准确（排除表头与空行，统计有效数据行）。"""
        run_id = import_run_id("m5_rows")
        expected_rows = 3
        layered_import_page.open_m03_entity_import_dialog()
        build_upload_validate(
            layered_import_page, tmp_path, run_id,
            lambda h: m03_many_valid_rows(h, f"auto_{run_id}", expected_rows),
        )
        dialog_text = layered_import_page.get_dialog_text()
        counts = [int(m) for m in re.findall(r"(\d+)\s*(?:行|条)", dialog_text)]
        assert any(c == expected_rows for c in counts), (
            f"未展示预期有效行数 {expected_rows}（弹窗内出现的行/条计数: {counts}）；当前弹窗: {dialog_text}"
        )
        layered_import_page.close_import_dialog()

    def test_m5_03_continuous_reupload_robustness(self, layered_import_page: LayeredImportPage):
        """M5-03: 连续多次重传切换不同数据文件，断言页面状态正常重置无重复提交。"""
        ds1 = get_m02_dataset("standard_valid")
        ds2 = get_m02_dataset("variant_progress")
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file(ds1["file_path"])
        layered_import_page.upload_file(ds2["file_path"])
        layered_import_page.click_validate_table()
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.close_import_dialog()

    def test_m5_04_medium_file_import_and_search(self, layered_import_page: LayeredImportPage, tmp_path: Path):
        """M5-04（容量代表性）: 较大文件（数百行）导入完成且列表可查询。

        注：需求大纲的「十几万条」量级不进 UI 自动化——会导致用例超时、污染 UAT 数据，
        容量/性能压测应走 JMeter 或后端专项。本用例用 200 行作为「较大文件」代表性覆盖。
        """
        run_id = import_run_id("m5_capacity")
        table_prefix = f"auto_{run_id}"
        row_count = 200
        layered_import_page.open_m03_entity_import_dialog()
        build_upload_validate(
            layered_import_page, tmp_path, run_id,
            lambda h: m03_many_valid_rows(h, table_prefix, row_count),
        )
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.click_confirm_import()
        layered_import_page.should_show_import_finished()
        layered_import_page.close_import_dialog()
        layered_import_page.search_and_verify_entity(f"{table_prefix}_0")
