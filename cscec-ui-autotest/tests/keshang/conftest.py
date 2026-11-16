"""客商接入（UAT/PRE）模块级 fixture。"""

from __future__ import annotations

import pytest

from config.settings import settings
from pages.portal.tenant_onboarding_page import TenantOnboardingPage


@pytest.fixture(scope="function")
def onboarding(logged_in_page) -> TenantOnboardingPage:
    """门户侧租户开通 Page Object（复用已登录上下文）。"""
    return TenantOnboardingPage(logged_in_page)


@pytest.fixture(scope="function")
def applicant_name() -> str:
    """当前申请人显示名（客商槽位优先，未配置时回退主账号）。"""
    return settings.keshang_username
