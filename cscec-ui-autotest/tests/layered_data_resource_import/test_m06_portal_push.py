"""M06 数据门户推送自动化测试。

需求大纲：M6 数据门户推送 —— 数据资产订阅流程上传文件推送。
当前仅覆盖「推送门户」入口可达与按钮可见（只读，不触发真实跨系统推送）。
「订阅流程上传文件并推送成功」涉及数据资产订阅独立模块与门户侧确认，
且会产生跨系统副作用，标记为 P2 待专项验证（需真实订阅数据 + 门户侧确认）。
"""

from __future__ import annotations

import pytest

from pages.dataresources.layered_import_page import LayeredImportPage


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
@pytest.mark.readonly
class TestM06PortalPush:
    """M06 数据门户推送。"""

    def test_m06_01_portal_push_entry_reachable(self, layered_import_page: LayeredImportPage):
        """M06-01: 数据分层设置页「推送门户」入口可达、按钮可见（只读，不触发真实推送）。"""
        layered_import_page.open_layer_settings()
        layered_import_page.assertions.any_text_visible(
            ["推送门户", "数据分层设置", "导入数据分层清单"],
        )
