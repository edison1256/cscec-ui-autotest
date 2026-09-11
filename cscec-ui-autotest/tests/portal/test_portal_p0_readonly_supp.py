"""PROD P0 门户只读走查补充用例（第一阶段深水区探活）。"""

from __future__ import annotations

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from config.settings import settings
from pages.portal.portal_home_page import PortalHomePage


ORG_SELECTION_ROUTE = (
    "/udpweb/portal/index.html?__sabotage=1789110307594_hpzhgdtu"
    "#/loginOrgTree?"
    "backRoute=/sub/resource/workOrder/initiated?suitKey=1899427585366003727"
    "&routeName=resource"
    "&appTitle=%E6%88%91%E5%8F%91%E8%B5%B7%E7%9A%84%E5%B7%A5%E5%8D%95"
    "&mc=1899427585366003727"
    "&mn=%E5%B7%A5%E4%BD%9C%E5%8F%B0"
    "&mt=module"
    "&menuCode=1953753908242132994"
    "&id=2098239822278336513"
    "&x-gw-nonce=9oQfHB7NZHfJ6pJ6ZFTUW9"
    "&x-gw-timestamp=1789110307"
    "&x-gw-signature=d6ae973bb48e389fa39d17930c42e57b"
    "&x-gw-appid=1808015709189693442"
)
ORG_TREE_API = "getLazyLoadOrgTreeByUserNoForNewLogin"
ERROR_TEXTS = ("系统繁忙", "页面不存在", "错误码：404", "错误码:404", "500 Internal Server Error")


def _response_has_org_data(payload: object) -> bool:
    """Return whether the org-tree response contains selectable organization data."""
    if isinstance(payload, list):
        return bool(payload)
    if not isinstance(payload, dict):
        return False

    for key in ("data", "result", "rows", "children", "list"):
        value = payload.get(key)
        if _response_has_org_data(value):
            return True
    return False


def _extract_org_labels(payload: object) -> list[str]:
    """Collect likely organization labels from an org-tree response."""
    labels: list[str] = []
    if isinstance(payload, list):
        for item in payload:
            labels.extend(_extract_org_labels(item))
        return labels
    if not isinstance(payload, dict):
        return labels

    for key in ("orgName", "name", "label", "title", "orgFullName"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            labels.append(value.strip())

    for key in ("data", "result", "rows", "children", "list"):
        labels.extend(_extract_org_labels(payload.get(key)))
    return labels


@pytest.mark.portal
@pytest.mark.readonly
@pytest.mark.regression
class TestPortalP0ReadonlySupp:
    """门户 P0 补充只读巡检。"""

    def test_portal_supp_001_header_footer_links(self, portal_home_page: PortalHomePage):
        """P0-PORTAL-SUPP-001: 验证门户首页页脚与顶部核心死链检查。"""
        portal_home_page.open()
        portal_home_page.should_have_valid_header_footer_links()

    def test_portal_supp_002_user_profile_hover(self, portal_home_page: PortalHomePage):
        """P0-PORTAL-SUPP-002: 个人账号卡片悬浮只读交互。"""
        portal_home_page.open()
        # 断言悬浮态能弹出，并检查是否包含环境变量中的 USERNAME
        portal_home_page.should_display_user_profile_menu(settings.USERNAME)

    def test_portal_supp_003_unauth_intercept(self, fresh_page):
        """P0-PORTAL-SUPP-003: 全局未授权越权拦截 (负面测试)。
        使用未登录的 fresh_page 访问强鉴权页面，断言回退到 CAS 登录。
        """
        target_url = settings.console_url("/udpweb/portal/index.html#/portal/home/workbench")
        fresh_page.goto(target_url, wait_until="domcontentloaded")
        
        try:
            fresh_page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        # 核心断言：未授权用户必须被重定向到 CAS 认证中心，而不是产生 500 或页面穿透
        current_url = fresh_page.url.lower()
        assert "cas/login" in current_url or "login" in current_url, f"未授权访问未被正确拦截，当前URL: {current_url}"

    def test_portal_supp_004_banner_rendering(self, portal_home_page: PortalHomePage):
        """P0-PORTAL-SUPP-004: 门户大盘内容容灾渲染（抽样图片破损检查）。"""
        portal_home_page.open()
        portal_home_page.should_render_portal_banners_correctly()

    def test_portal_supp_005_login_org_tree_has_selectable_data(self, logged_in_page):
        """P0-PORTAL-SUPP-005: 组织选择页组织树接口返回可选组织。"""
        target_url = settings.portal_url(ORG_SELECTION_ROUTE)

        with logged_in_page.expect_response(
            lambda response: ORG_TREE_API in response.url,
            timeout=settings.NAVIGATION_TIMEOUT,
        ) as response_info:
            logged_in_page.goto(target_url, wait_until="domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)

        org_response = response_info.value
        assert org_response.ok, f"组织树接口 HTTP 异常: status={org_response.status}, url={org_response.url}"

        payload = org_response.json()
        if isinstance(payload, dict):
            assert payload.get("code") != 50000, f"组织树接口仍返回系统繁忙: {payload}"
        assert "系统繁忙" not in str(payload), f"组织树接口仍包含系统繁忙提示: {payload}"
        assert _response_has_org_data(payload), f"组织树接口未返回可选择组织数据: {payload}"

        try:
            logged_in_page.wait_for_load_state("networkidle", timeout=10000)
        except PlaywrightTimeoutError:
            pass

        body = " ".join(logged_in_page.locator("body").inner_text(timeout=settings.ACTION_TIMEOUT).split())
        assert "选择组织" in body, f"未停留在组织选择页: url={logged_in_page.url}, body={body[:500]}"
        assert not any(text in body for text in ERROR_TEXTS), (
            f"组织选择页仍显示错误态: url={logged_in_page.url}, body={body[:500]}"
        )

        labels = _extract_org_labels(payload)
        if labels:
            assert any(label in body for label in labels[:10]), (
                f"组织树接口已有数据，但页面未渲染前 10 个组织名称: labels={labels[:10]}, body={body[:500]}"
            )
