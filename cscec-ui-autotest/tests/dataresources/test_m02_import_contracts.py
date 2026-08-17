"""M02 data layer import dialog contract tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.dataresources.import_workbooks import read_first_sheet_headers


@pytest.mark.dataresources
@pytest.mark.regression
@pytest.mark.readonly
class TestM02ImportContracts:
    """UI-CAND-0001 and UI-CAND-0068."""

    def test_m02_import_dialog_and_template_download_are_available(self, data_layer_settings, tmp_path: Path):
        data_layer_settings.open_import_dialog("M02")
        data_layer_settings.should_show_import_dialog("M02")
        data_layer_settings.should_have_import_upload()

        template_path = data_layer_settings.download_import_template(tmp_path, "M02")
        headers = read_first_sheet_headers(template_path)

        for header in ["一级应用域名称", "L1", "L2", "L3"]:
            assert header in headers

        data_layer_settings.close_import_dialog()
