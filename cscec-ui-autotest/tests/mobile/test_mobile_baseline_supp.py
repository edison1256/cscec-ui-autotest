"""M5-移动端只读走查补充用例（第四阶段深水区探活）。"""

from __future__ import annotations

import pytest

from core.navigation_helpers import EntryNotExposed
from pages.mobile.mobile_home_page import MobileHomePage


@pytest.mark.mobile
@pytest.mark.readonly
@pytest.mark.regression
class TestMobileBaselineSupp:
    """M5 移动端链路补充探活用例集。"""

    def test_m5_supp_001_tabbar_switching(self, logged_in_mobile_page):
        """M5-SUPP-001: 底部导航栏 (TabBar) 柔性切换。"""
        mobile_page = MobileHomePage(logged_in_mobile_page)
        mobile_page.open_home()
        mobile_page.switch_tab_and_verify_stability()

    def test_m5_supp_002_grid_app_clickthrough(self, logged_in_mobile_page):
        """M5-SUPP-002: 金刚区 (Grid) 应用穿透触达。"""
        mobile_page = MobileHomePage(logged_in_mobile_page)
        mobile_page.open_home()
        try:
            mobile_page.verify_grid_app_clickthrough()
        except EntryNotExposed as exc:
            pytest.skip(str(exc))
