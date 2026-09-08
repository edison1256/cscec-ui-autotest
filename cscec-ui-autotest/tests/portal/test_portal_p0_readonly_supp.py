"""PROD P0 门户只读走查补充用例（第一阶段深水区探活）。"""

import pytest

from config.settings import settings
from pages.portal.portal_home_page import PortalHomePage


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
