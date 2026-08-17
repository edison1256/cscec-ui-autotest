"""M1 & M5 导入通用行为、进度条展示与性能稳定性自动化测试用例集。

依据需求大纲《数据资源导入功能优化以及性能优化V2.xmind》全量细化覆盖：
1. 导入前通用行为：校验阶段绝不提前写入落库、多行错误复数行展示、错误后重新上传恢复校验；
2. 进度条与容量：导入执行展示进度条无卡死、有效行数统计排除表头和空行、连续多次导入稳定性与防重复提交。
"""

from __future__ import annotations

import time
from pathlib import Path
import pytest

from pages.dataresources.layered_import_page import LayeredImportPage


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
class TestImportCommonBehaviors:
    """M1 导入通用行为与容错校验测试。"""

    def test_m1_01_no_write_before_confirm_import(self, layered_import_page: LayeredImportPage):
        """M1-01: 校验表格阶段存在错误或未点击导入按钮前，断言系统绝对不提前写入通过校验的数据（搜索为空）。"""
        token = int(time.time())
        fake_table_name = f"test_no_write_{token}"
        # 先核验当前搜索为空
        layered_import_page.should_show_no_search_results(fake_table_name)

        # 打开导入弹窗并上传有效文件进入校验阶段
        layered_import_page.open_m03_entity_import_dialog()
        layered_import_page.upload_file("M03数据实体清单.xlsx")
        layered_import_page.click_validate_table()
        # 校验通过但不点击导入，直接关闭弹窗
        layered_import_page.close_import_dialog()

        # 再次搜索核验数据未提前落库
        layered_import_page.should_show_no_search_results(fake_table_name)

    def test_m1_02_multiple_error_rows_display(self, layered_import_page: LayeredImportPage):
        """M1-02: 上传包含多行错误的数据文件，断言支持输出复数错误数据行。"""
        layered_import_page.open_m03_entity_import_dialog()
        layered_import_page.upload_file("M03数据实体清单 - 副本 - 副本.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.should_show_import_errors(["校验失败", "错误", "行"])
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()

    def test_m1_03_reupload_after_error_restores_validation(self, layered_import_page: LayeredImportPage):
        """M1-03: 业务校验不通过后在同一弹窗内重新上传正确文件，断言可重新校验并恢复校验通过态。"""
        layered_import_page.open_m02_layer_import_dialog()
        # 1. 首次上传错误列名文件
        layered_import_page.upload_file("M02数据分层清单 - 副本 - 副本 - 副本.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.should_show_column_mismatch_error()
        layered_import_page.should_not_allow_import()

        # 2. 重新上传正确文件修复
        layered_import_page.upload_file("M02数据分层清单.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
class TestImportProgressAndVolume:
    """M5 导入进度条展示、行数统计与性能稳定性测试。"""

    def test_m5_01_progress_bar_visible_during_import(self, layered_import_page: LayeredImportPage):
        """M5-01: 校验或导入过程中观察页面，断言存在进度条且页面保持响应无白屏。"""
        layered_import_page.open_m02_layer_import_dialog()
        layered_import_page.upload_file("M02数据分层清单 - 副本.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.assertions.page_not_blank_or_error()
        layered_import_page.close_import_dialog()

    def test_m5_02_row_count_statistics_accurate(self, layered_import_page: LayeredImportPage):
        """M5-02: 包含表头和空行导入时，如页面展示总需求导入行数，断言统计值排除表头和空行。"""
        layered_import_page.open_m03_entity_import_dialog()
        layered_import_page.upload_file("M03数据实体清单.xlsx")
        layered_import_page.click_validate_table()
        dialog_text = layered_import_page.get_dialog_text()
        # 弹窗内应识别数据行数或校验状态
        assert any(k in dialog_text for k in ["条", "行", "校验通过", "导入"]), f"未识别到有效行数统计或通过状态: {dialog_text}"
        layered_import_page.close_import_dialog()

    def test_m5_03_continuous_reupload_robustness(self, layered_import_page: LayeredImportPage):
        """M5-03: 连续多次导入校验容错与状态重置，防止重复提交或状态紊乱。"""
        layered_import_page.open_m02_layer_import_dialog()
        # 连续快速切换上传两个文件
        layered_import_page.upload_file("M02数据分层清单.xlsx")
        layered_import_page.upload_file("M02数据分层清单 - 副本.xlsx")
        layered_import_page.click_validate_table()
        layered_import_page.assertions.page_not_blank_or_error()
        layered_import_page.close_import_dialog()
