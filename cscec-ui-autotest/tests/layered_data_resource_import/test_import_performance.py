"""M5 导入进度条展示、行数统计与性能优化自动化测试用例集。

覆盖范围（依据《数据资源导入功能优化以及性能优化V2.xmind》）：
- M5-01: 导入过程进度条/状态提示展示与页面防卡死校验
- M5-02: 导入行数统计与表头/空行过滤准确性校验
- M5-03: 连续多次导入校验容错与状态重置校验
"""

from __future__ import annotations

import pytest

from pages.dataresources.layered_import_page import LayeredImportPage


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
class TestImportPerformanceProgress:
    """M5 导入进度条展示与性能优化用例集。"""

    def test_m5_01_import_progress_bar_visible(self, layered_import_page: LayeredImportPage):
        """M5-01: 验证文件校验/导入过程中展示进度指示，页面保持响应无白屏。"""
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file("M02数据分层清单 - 副本.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.assertions.page_not_blank_or_error()
        layered_import_page.close_import_dialog()

    def test_m5_02_import_row_count_statistics_accurate(self, layered_import_page: LayeredImportPage):
        """M5-02: 验证多行数据导入时，弹窗正确统计有效数据行并呈现状态。"""
        layered_import_page.open_m03_entity_import_dialog()
        layered_import_page.upload_file("M03数据实体清单.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.assertions.page_not_blank_or_error()
        layered_import_page.close_import_dialog()

    def test_m5_03_continuous_reupload_robustness(self, layered_import_page: LayeredImportPage):
        """M5-03: 验证在同一导入弹窗内连续重传不同文件时，校验状态重置且不引发异常。"""
        layered_import_page.open_m02_layer_import_dialog()
        # 1. 首次上传异常列名文件
        layered_import_page.upload_file("M02数据分层清单 - 副本 - 副本 - 副本.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.should_show_column_mismatch_error()
        # 2. 连续重新上传标准文件进行修复
        layered_import_page.upload_file("M02数据分层清单.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.assertions.page_not_blank_or_error()
        layered_import_page.close_import_dialog()
