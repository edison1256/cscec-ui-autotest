"""PROD P0 门户只读页面回归。"""

import pytest

from pages.portal.portal_home_page import PortalHomePage


PORTAL_P0_CASES = [
    pytest.param(
        "/",
        ["一站全服务", "高效、安全、灵活的云产品"],
        None,
        id="C-P0-PORTAL-001-home",
    ),
    pytest.param(
        "/#/service-center/2",
        ["服务中心"],
        "请输入搜索内容",
        id="C-P0-PORTAL-002-service-center",
    ),
    pytest.param(
        "/#/smart-construction",
        ["智能建造", "产品市场"],
        "请输入搜索内容",
        id="C-P0-PORTAL-003-smart-construction",
    ),
    pytest.param(
        "/#/solution",
        ["合作伙伴"],
        None,
        id="C-P0-PORTAL-004-solution",
    ),
    pytest.param(
        "/#/developer-platform",
        ["开发者平台"],
        None,
        id="C-P0-PORTAL-005-developer-platform",
    ),
    pytest.param(
        "/#/support",
        ["支持与帮助"],
        None,
        id="C-P0-PORTAL-006-support",
    ),
]


@pytest.mark.portal
@pytest.mark.smoke
@pytest.mark.readonly
@pytest.mark.regression
class TestPortalP0ReadonlyRegression:
    """门户 P0 只读页面回归。"""

    @pytest.mark.parametrize("route, expected_texts, safe_input_placeholder", PORTAL_P0_CASES)
    def test_portal_p0_page_accessible_and_safe_interaction(
        self,
        logged_in_page,
        route,
        expected_texts,
        safe_input_placeholder,
    ):
        portal = PortalHomePage(logged_in_page)
        portal.open_route(route)
        portal.should_be_readonly_page_ready(expected_texts)
        if safe_input_placeholder:
            portal.fill_and_clear_input(safe_input_placeholder)
