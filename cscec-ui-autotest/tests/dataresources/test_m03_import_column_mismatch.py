"""M03 data entity import validation tests."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from tests.dataresources.import_workbooks import create_m03_column_mismatch_workbook


@pytest.mark.dataresources
@pytest.mark.regression
@pytest.mark.write
class TestM03ImportColumnMismatch:
    """M1-06 column mismatch checks for M03 import."""

    def test_m03_import_column_mismatch_blocks_import_and_creates_no_resource(
        self,
        data_resources,
        tmp_path: Path,
    ):
        table_english_name = f"auto_m03_col_mismatch_{int(time.time())}"
        mismatch_file = create_m03_column_mismatch_workbook(tmp_path, table_english_name)

        data_resources.search_by_keyword(table_english_name)
        data_resources.should_show_no_search_results()

        data_resources.open_m03_import()
        data_resources.upload_import_file(str(mismatch_file))
        data_resources.click_validate_table()
        data_resources.should_show_column_mismatch_error()
        data_resources.should_not_allow_import()
        data_resources.close_import_dialog()

        data_resources.search_by_keyword(table_english_name)
        data_resources.should_show_no_search_results()
