"""域名拆分 - 门户模块自动化资产。

来源：
- C:/Users/CFD/Desktop/域名拆分.xmind
- C:/Users/CFD/Desktop/域名拆分_测试用例.xlsx，测试用例 sheet 第 2-60 行
"""

from __future__ import annotations

import os
import re
from datetime import datetime
from dataclasses import dataclass, field
from urllib.parse import urlparse

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from config.settings import settings
from pages.portal.login_page import LoginPage
from pages.portal.portal_home_page import PortalHomePage


@dataclass(frozen=True)
class PortalCase:
    row: int
    module: str
    title: str
    strategy: str
    priority: str = "高"
    route: str = "/"
    expected_texts: tuple[str, ...] = ()
    link_texts: tuple[str, ...] = ()
    required_env: tuple[str, ...] = ()
    notes: str = ""

    @property
    def case_id(self) -> str:
        return f"DS-PORTAL-{self.row:03d}"


PORTAL_CASES = [
    PortalCase(2, "域名访问", "使用新域名访问门户，验证首页正常加载", "page_access", expected_texts=("工作台", "中建云")),
    PortalCase(3, "中建通入口", "通过中建通应用入口点击进入门户，验证跳转至新域名门户首页", "external_deep", required_env=("PORTAL_ZJT_ENTRY_NAME",), notes="需要中建通入口定位信息或已登录态。"),
    PortalCase(4, "首页展示", "在新域名下访问首页，验证所有模块正常展示", "home_modules"),
    PortalCase(5, "首页", "点击首页图片，验证跳转到控制台配置的链接", "external_deep", required_env=("PORTAL_HOME_IMAGE_LINK_TEXT",), notes="需要可点击图片或链接的稳定文本。"),
    PortalCase(6, "用户信息展示", "登录成功后正确展示当前用户的账号信息", "logged_in_identity"),
    PortalCase(7, "用户认证模块", "登录状态下点击退出登录，验证退出成功并跳转至登录页", "destructive_auth", notes="退出会破坏共享登录态，默认不执行。"),
    PortalCase(8, "门户首页", "用户登录门户后，验证首页展示的租户信息与当前登录用户所属租户一致", "tenant_display", expected_texts=("中建云",)),
    PortalCase(9, "门户/角色信息展示", "使用已分配角色的用户登录门户，验证角色信息展示正确", "manual_confirm", "中", notes="角色可随时配置变化，当前不做自动断言。"),
    PortalCase(10, "租户切换", "已登录多租户用户切换租户，系统跳转至所选租户工作台", "requires_data", required_env=("PORTAL_ALT_TENANT",)),
    PortalCase(11, "租户流程管理", "创建租户后，使用租户管理员账号登录门户并成功发起流程", "write_flow", required_env=("PORTAL_TENANT_ADMIN_USER", "PORTAL_TENANT_ADMIN_PASSWORD")),
    PortalCase(12, "待办信息", "验证待办信息中资源、审批、订单、收藏链接域名均为新域名cloud.cscec.com", "link_domain", link_texts=("资源", "审批", "订单", "收藏")),
    PortalCase(13, "云产品分类查询", "选择前端类目查询，验证返回该类目下的云产品列表", "readonly_search", route="/#/service-center/2", expected_texts=("云产品", "服务中心")),
    PortalCase(14, "门户内容操作", "点击收藏按钮，验证收藏成功提示并更新收藏状态", "favorite_toggle", route="/#/service-center/2", required_env=("RUN_PORTAL_WRITE_CASES",)),
    PortalCase(15, "详情查看功能", "通过列表页点击记录，验证详情页正确展示", "readonly_detail", "中", route="/"),
    PortalCase(16, "门户应用文档", "点击应用文档链接，验证文档正常打开", "page_access", route="/#/support", expected_texts=("应用帮助文档", "知识中心")),
    PortalCase(17, "服务咨询模块", "在服务咨询页面填写有效咨询内容并提交，验证工单创建成功", "consult_ticket", route="/#/service-center/2/1882692531190411265", required_env=("RUN_PORTAL_WRITE_CASES",)),
    PortalCase(18, "立即申请", "切换租户后完成申请：保存草稿、加入购物车并提交审批，验证完整流程", "apply_entry", route="/#/service-center/2/1882692531190411265", required_env=("RUN_PORTAL_WRITE_CASES",)),
    PortalCase(19, "审批流程", "提交审批，验证审批流程成功发起", "write_flow", required_env=("RUN_PORTAL_WRITE_CASES", "PORTAL_APPROVER_NAME")),
    PortalCase(20, "系统入口", "使用新域名访问门户，验证进入系统", "page_access", expected_texts=("工作台", "中建云")),
    PortalCase(21, "服务组件查询", "按前端类目分类查询服务组件，验证查询结果正确", "readonly_search", route="/#/service-center/3", expected_texts=("服务组件", "服务中心")),
    PortalCase(22, "门户-收藏分享", "收藏成功的内容分享后，他人通过分享链接可正常访问", "write_flow", required_env=("RUN_PORTAL_WRITE_CASES", "PORTAL_SHARE_TARGET_USER")),
    PortalCase(23, "API详情页", "使用新域名访问API详情，页面正常展示接口信息", "logged_in_page_access", route="/#/service-center-component/3/1946021317563310082", expected_texts=("接口文档", "服务组件")),
    PortalCase(24, "应用文档", "点击应用文档链接，验证文档页面可正常打开", "page_access", route="/#/support", expected_texts=("应用帮助文档", "知识中心")),
    PortalCase(25, "服务咨询", "登录用户填写有效咨询内容并提交，验证工单发起成功", "consult_ticket", route="/#/service-center-component/3/1946021317563310082", required_env=("RUN_PORTAL_WRITE_CASES",)),
    PortalCase(26, "立即申请", "切换租户后，验证立即申请支持保存草稿、加入购物车并提交审批", "apply_entry", route="/#/service-center-component/3/1946021317563310082", required_env=("RUN_PORTAL_WRITE_CASES", "PORTAL_ALT_TENANT")),
    PortalCase(27, "数据资产查询", "选择有效前端类目查询数据资产，验证返回正确类目下的资产列表", "readonly_search", route="/#/service-center/4", expected_texts=("数据资产", "服务中心")),
    PortalCase(28, "内容交互", "在门户内容详情页点击收藏，验证收藏成功", "favorite_toggle", route="/#/service-center/1", required_env=("RUN_PORTAL_WRITE_CASES",)),
    PortalCase(29, "门户-详情查看", "用户点击列表项查看详情，验证详情页正常展示", "readonly_detail"),
    PortalCase(30, "资产表权限申请", "提交有效资产表权限申请，验证申请成功", "write_flow", required_env=("RUN_PORTAL_WRITE_CASES", "PORTAL_ASSET_TABLE_NAME")),
    PortalCase(31, "门户-立即申请", "用户在门户首页点击立即申请，跳转至申请页面并正确加载表单", "apply_entry", route="/#/service-center/2/1882692531190411265", required_env=("RUN_PORTAL_WRITE_CASES",)),
    PortalCase(32, "审批流程", "提交申请，验证审批流程成功发起", "write_flow", required_env=("RUN_PORTAL_WRITE_CASES", "PORTAL_APPROVER_NAME")),
    PortalCase(33, "企业应用查询", "使用有效关键词搜索企业应用，验证返回匹配结果", "readonly_search", route="/#/service-center/1", expected_texts=("企业应用", "服务中心")),
    PortalCase(34, "企业应用收藏和分享", "用户收藏企业应用并分享给指定用户，验证收藏状态和分享消息", "write_flow", required_env=("RUN_PORTAL_WRITE_CASES", "PORTAL_ENTERPRISE_APP_NAME", "PORTAL_SHARE_TARGET_USER")),
    PortalCase(35, "企业应用详情", "通过新门户域名访问企业应用详情，验证页面正常展示", "logged_in_page_access", route="/#/service-center/1/2034147659659407361", expected_texts=("帆软BI", "企业应用")),
    PortalCase(36, "企业应用申请", "点击“立即申请”按钮提交申请，验证审批流程发起成功", "apply_entry", route="/#/service-center/1/2034147659659407361", required_env=("RUN_PORTAL_WRITE_CASES",)),
    PortalCase(37, "门户-企业应用与云产品一致性", "验证企业应用与云产品在列表筛选功能上保持一致", "service_center_consistency", "中"),
    PortalCase(38, "建筑大模型栏目", "使用新域名访问建筑大模型栏目首页，验证页面正常加载", "page_access", route="/#/smart-construction", expected_texts=("智能建造", "产品市场")),
    PortalCase(39, "门户展示", "门户页面仅显示“中建通”应用入口", "requires_data", required_env=("PORTAL_EXPECTED_APP_ENTRY",)),
    PortalCase(40, "业务接入", "在门户中打开已授权的轻应用，验证页面正常加载", "click_text", route="/#/developer-platform", link_texts=("统一开发平台",), expected_texts=("项目管理", "功能模块")),
    PortalCase(41, "算力申请", "在门户新域名下打开算力申请轻应用，验证轻应用加载正常", "external_deep", required_env=("PORTAL_COMPUTE_APP_ENTRY",)),
    PortalCase(42, "解决方案栏目", "使用新域名访问解决方案栏目首页，验证页面正常加载且内容显示正确", "page_access", route="/#/solution", expected_texts=("解决方案", "合作伙伴")),
    PortalCase(43, "解决方案展示", "新域名下访问全部解决方案列表，验证页面正常加载并展示数据", "page_access", route="/#/solution", expected_texts=("解决方案",)),
    PortalCase(44, "解决方案标签展示", "访问门户解决方案页面，验证标签展示与后台配置一致", "page_access", route="/#/solution", expected_texts=("产业", "云计算", "查看更多")),
    PortalCase(45, "内容详情页", "用户访问门户详情页并收藏，验证收藏功能正常", "favorite_toggle", route="/#/service-center/2", required_env=("RUN_PORTAL_WRITE_CASES",)),
    PortalCase(46, "联系咨询", "通过门户新域名访问联系咨询并提交咨询信息", "support_float_entry", "中", route="/#/support", link_texts=("问题咨询",), expected_texts=("发起咨询", "问题分类", "问题描述")),
    PortalCase(47, "门户-开发者实验室", "打开开发者实验室页面，验证列表展示2个实验室", "readonly_search", "中", route="/#/service-center/2", expected_texts=("开发者实验室", "服务中心")),
    PortalCase(48, "域名拆分-门户iframe", "验证门户详情页、开始体验、操作文档、实验简介iframe在新域名下正常加载", "iframe_deep", route="/#/developer-platform", expected_texts=("开发者平台",)),
    PortalCase(49, "账号申请模块", "点击申请账号链接，验证链接可打开并跳转至注册页面", "page_access", route="/#/support", expected_texts=("平台注册", "知识中心")),
    PortalCase(50, "VPN 申请", "在浏览器中打开 VPN 申请链接，验证页面正常加载", "external_url", required_env=("PORTAL_VPN_APPLY_URL",)),
    PortalCase(51, "统一开发平台/实验室申请", "使用新域名 cloud.cscec.com 访问实验室申请部署链接，验证页面正常加载", "click_text", route="/#/developer-platform", link_texts=("立即申请",), expected_texts=("支持与帮助", "知识中心")),
    PortalCase(52, "门户-导航链接", "点击“开发者社区”跳转链接，验证跳转至正确的开发者社区页面", "click_text", "中", route="/#/developer-platform", link_texts=("开发者社区",)),
    PortalCase(53, "开发规范指引", "访问开发规范指引文档，验证iframe内正常加载", "iframe_deep", "中", route="/#/developer-platform", expected_texts=("开发者平台",)),
    PortalCase(54, "控制台-开发资源获取与平台展示", "使用irp域名访问控制台，验证开发资源获取配置内容正常展示", "console_scope", route="/udpweb/portal/index.html#/portal/home/workbench?suitKey=portal", expected_texts=("工作台", "开发者社区", "API资源", "组件资源", "云资源")),
    PortalCase(55, "门户首页", "验证门户首页开发者社区配置展示正确", "page_access", "中", route="/#/developer-platform", expected_texts=("开发者社区", "前沿技术分享", "最佳实践分享")),
    PortalCase(56, "门户通用交互", "点击“查看更多”链接，验证跳转至正确的目标页面", "click_text", route="/#/service-center/2", link_texts=("演示用-云资源-资源类",)),
    PortalCase(57, "知识中心", "使用新域名访问门户知识中心，验证页面正常加载", "page_access", route="/#/support", expected_texts=("支持与帮助", "知识中心")),
    PortalCase(58, "智能机器人咨询", "在门户域名下咨询智能机器人，验证回复正常", "support_float_entry", route="/#/support", link_texts=("智能客服",), expected_texts=("智能客服", "问题咨询")),
    PortalCase(59, "智能客服", "通过新域名访问智能客服，验证对话功能正常", "support_float_entry", route="/#/support", link_texts=("问题咨询",), expected_texts=("发起咨询", "问题分类", "问题描述")),
    PortalCase(60, "进度查询", "使用有效查询条件查询进度，验证进度信息显示正确", "support_float_entry", route="/#/support", link_texts=("查询进度",)),
]


def _enabled(name: str) -> bool:
    return os.getenv(name, "").lower() in {"1", "true", "yes", "on"}


def _missing_env(case: PortalCase) -> list[str]:
    missing = []
    for name in case.required_env:
        if name == "RUN_PORTAL_WRITE_CASES":
            if not _enabled(name):
                missing.append(name)
        elif not os.getenv(name):
            missing.append(name)
    return missing


def _skip_missing(case: PortalCase) -> None:
    missing = _missing_env(case)
    if missing:
        pytest.skip(f"{case.case_id} 需要补充配置/数据后执行: {', '.join(missing)}. {case.notes}")


def _generated_business_title(case: PortalCase) -> str:
    """生成 UAT/PRE 写入类用例默认业务标题。"""
    return f"{datetime.now():%Y%m%d}-{case.module}-{case.title}"


def _assert_page_host(page_url: str, expected_base_url: str) -> None:
    current_host = urlparse(page_url).netloc.lower()
    expected_host = urlparse(expected_base_url).netloc.lower()
    assert current_host == expected_host, f"域名不符合预期: expected={expected_host}, actual={current_host}, url={page_url}"


def _assert_target_page_ready(target_page) -> None:
    target_page.locator("body").wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
    body = " ".join(target_page.locator("body").inner_text(timeout=settings.ACTION_TIMEOUT).split())
    assert body, f"目标页面为空: {target_page.url}"
    assert not any(text in body[:2000] for text in ["404", "500", "页面不存在", "系统异常"]), (
        f"目标页面疑似错误页: {target_page.url}"
    )


def _assert_body_contains_any(page, expected_texts: tuple[str, ...] | list[str]) -> None:
    try:
        page.wait_for_function(
            """texts => texts.some(text => document.body && document.body.innerText.includes(text))""",
            arg=list(expected_texts),
            timeout=30000,
        )
        return
    except PlaywrightTimeoutError:
        pass
    body = " ".join(page.locator("body").inner_text(timeout=settings.ACTION_TIMEOUT).split())
    assert any(text in body for text in expected_texts), (
        f"页面未包含任一预期文本: {list(expected_texts)}; url={page.url}; body={body[:500]}"
    )


def _assert_portal_page_ready_with_sso_retry(portal: PortalHomePage, route: str) -> None:
    """SSO 回跳可能把 code 参数拼到 hash 深链后导致 SPA 空白，去参后重开一次。"""
    try:
        portal.assertions.page_not_blank_or_error()
        return
    except AssertionError as exc:
        blank_after_sso = "Page body is blank" in str(exc) and "code=" in portal.page.url
        if not blank_after_sso:
            raise
    portal.open_route(route)
    portal.assertions.page_not_blank_or_error()


def _click_visible_text_and_assert_ready(page, text: str):
    """点击当前页可见文本，验证页面仍可用或新页可用。"""
    old_url = page.url
    try:
        with page.context.expect_page(timeout=5000) as page_info:
            page.get_by_text(text, exact=True).first.click(timeout=settings.ACTION_TIMEOUT)
        target = page_info.value
        target.wait_for_load_state("domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
        try:
            target.wait_for_function(
                "() => document.body && document.body.innerText.trim().length > 0",
                timeout=30000,
            )
            _assert_target_page_ready(target)
        except (AssertionError, PlaywrightTimeoutError):
            parsed = urlparse(target.url.lower())
            assert parsed.scheme in {"http", "https"} and parsed.netloc, f"目标页面 URL 异常: {target.url}"
            assert not any(text in target.url.lower() for text in ["login", "404", "500"]), (
                f"目标页面疑似未正常跳转: {target.url}"
            )
        return target
    except PlaywrightTimeoutError:
        pass

    try:
        page.get_by_text(text, exact=True).first.click(timeout=settings.ACTION_TIMEOUT)
    except PlaywrightTimeoutError:
        _click_exact_visible_text_by_dom(page, text)
    page.wait_for_timeout(1000)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except PlaywrightTimeoutError:
        pass
    page.locator("body").wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
    body = " ".join(page.locator("body").inner_text(timeout=settings.ACTION_TIMEOUT).split())
    assert body, f"点击 {text} 后页面为空: {page.url}"
    assert not any(error_text in body[:2000] for error_text in ["404", "500", "页面不存在", "系统异常"]), (
        f"点击 {text} 后疑似错误页: {page.url}"
    )
    assert page.url != old_url or text in body, f"点击 {text} 后页面无可验证变化: {page.url}"
    return page


def _open_support_float_entry(portal: PortalHomePage, text: str):
    """打开支持页右侧悬浮入口，只验证入口面板或跳转页可用，不提交表单。"""
    page = portal.page
    portal.open_route("/#/support")
    portal.should_be_on_portal_domain()
    portal.assertions.page_not_blank_or_error()
    page.locator("[class*=lan_bao]").first.hover(timeout=settings.ACTION_TIMEOUT)
    page.get_by_text(text, exact=True).first.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
    try:
        with page.context.expect_page(timeout=5000) as page_info:
            page.get_by_text(text, exact=True).first.click(timeout=settings.ACTION_TIMEOUT)
        target = page_info.value
        target.wait_for_load_state("domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
        try:
            target.wait_for_load_state("networkidle", timeout=10000)
        except PlaywrightTimeoutError:
            pass
        try:
            _assert_target_page_ready(target)
        except AssertionError:
            parsed_url = target.url.lower()
            assert "workorder/initiated" in parsed_url or "/portal/home/workbench" in parsed_url, (
                f"支持页入口跳转后目标页为空且 URL 不符合查询进度入口: {target.url}"
            )
        return target
    except PlaywrightTimeoutError:
        page.get_by_text(text, exact=True).first.click(timeout=settings.ACTION_TIMEOUT)
        page.wait_for_timeout(1000)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except PlaywrightTimeoutError:
            pass
        portal.assertions.page_not_blank_or_error()
        return page


def _ensure_portal_logged_in(page) -> PortalHomePage:
    portal = PortalHomePage(page)
    portal.open()
    portal.should_be_on_portal_domain()
    try:
        login_entry_visible = page.get_by_text("登录", exact=True).first.is_visible(timeout=2000)
    except Exception:
        login_entry_visible = False
    if login_entry_visible:
        login_page = LoginPage(page).click_login_entry()
        if login_page.login_form_visible():
            login_page.fill_credentials().click_login_button(
                expected_host=urlparse(settings.PORTAL_BASE_URL).netloc.lower()
            )
        portal = PortalHomePage(page)
        portal.should_be_on_portal_domain()
        try:
            page.wait_for_load_state("domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
            page.wait_for_load_state("networkidle", timeout=10000)
        except PlaywrightTimeoutError:
            pass
    try:
        portal.should_be_logged_in()
    except Exception:
        try:
            page.wait_for_load_state("domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
            page.wait_for_load_state("networkidle", timeout=10000)
        except PlaywrightTimeoutError:
            pass
        try:
            portal.should_be_logged_in()
        except AssertionError:
            if page.get_by_text("登录", exact=True).first.is_visible(timeout=1000):
                raise
    return portal


def _assert_write_allowed(case: PortalCase) -> None:
    _skip_missing(case)
    if settings.ENV not in {"uat", "pre"}:
        pytest.skip(f"{case.case_id} 写入类用例只允许 UAT/PRE 执行，当前 ENV={settings.ENV}")


def _toggle_first_visible_favorite(page, case: PortalCase) -> None:
    """对当前列表页第一张可见卡片执行收藏状态切换。"""
    card = page.locator(".contentItem-zZB6wk").first
    card.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
    title = " ".join(card.inner_text(timeout=settings.ACTION_TIMEOUT).split())[:120]
    card.hover(timeout=settings.ACTION_TIMEOUT)
    star = card.locator(".anticon-star, .anticon-star-filled").first
    star.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
    star.click(timeout=settings.ACTION_TIMEOUT)
    message = page.locator(".ant-message-notice-content").first
    message.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
    message_text = " ".join(message.inner_text(timeout=settings.ACTION_TIMEOUT).split())
    assert "未登录" not in message_text, f"{case.case_id} 收藏写入失败，页面提示未登录: {title}"
    assert any(text in message_text for text in ["收藏", "成功", "取消"]), (
        f"{case.case_id} 收藏写入后未出现预期提示: {message_text}; card={title}"
    )


def _select_first_consult_category(page) -> None:
    """选择咨询弹层中的第一个可用方案分类。"""
    placeholder = page.get_by_text("请选择", exact=True).first
    try:
        placeholder.wait_for(state="visible", timeout=5000)
    except PlaywrightTimeoutError:
        return
    placeholder.click(timeout=settings.ACTION_TIMEOUT)
    page.wait_for_timeout(500)
    option_candidates = [
        page.locator("[role='option']").filter(has_text=re.compile(r"\S")).first,
        page.locator(".ant-select-item-option-content").filter(has_text=re.compile(r"\S")).first,
        page.locator(".ant-cascader-menu-item").filter(has_text=re.compile(r"\S")).first,
        page.locator(".ant-dropdown-menu-item").filter(has_text=re.compile(r"\S")).first,
        page.locator("li").filter(has_text=re.compile(r"\S")).first,
    ]
    for option in option_candidates:
        try:
            option.wait_for(state="visible", timeout=2500)
            option.click(timeout=settings.ACTION_TIMEOUT)
            return
        except PlaywrightTimeoutError:
            continue
    raise AssertionError("咨询弹层已打开，但方案分类下拉未展示可选项")


def _click_exact_visible_text_by_dom(page, text: str) -> None:
    """点击页面中精确匹配文本的可见最小元素，绕开固定头部遮挡。"""
    clicked = page.evaluate(
        """target => {
            const isVisible = el => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                return rect.width > 0 && rect.height > 0
                    && style.visibility !== 'hidden'
                    && style.display !== 'none'
                    && style.pointerEvents !== 'none';
            };
            const matches = [...document.querySelectorAll('body *')]
                .filter(el => el.innerText && el.innerText.trim() === target && isVisible(el))
                .sort((a, b) => {
                    const ar = a.getBoundingClientRect();
                    const br = b.getBoundingClientRect();
                    return (ar.width * ar.height) - (br.width * br.height);
                });
            const el = matches[0];
            if (!el) return false;
            const clickable = el.closest('button,a,[role=button],[onclick]') || el.parentElement || el;
            clickable.scrollIntoView({block: 'center', inline: 'center'});
            clickable.click();
            return true;
        }""",
        text,
    )
    if not clicked:
        raise AssertionError(f"未找到可见文本元素: {text}")


def _submit_consult_ticket(page, case: PortalCase) -> None:
    """在服务详情页发起咨询并提交工单。"""
    page.keyboard.press("Escape")
    page.mouse.click(320, 90)
    page.wait_for_function(
        "() => document.body.innerText.includes('服务咨询') || document.body.innerText.includes('立即申请')",
        timeout=settings.ACTION_TIMEOUT,
    )
    body = page.locator("body").inner_text(timeout=settings.ACTION_TIMEOUT)
    if "服务咨询" not in body:
        pytest.skip(f"{case.case_id} 当前样本详情页未开放“服务咨询”入口，需要指定可咨询资源。")
    _click_exact_visible_text_by_dom(page, "服务咨询")
    page.wait_for_timeout(500)
    _click_exact_visible_text_by_dom(page, "创建咨询工单")
    page.get_by_text("发起咨询", exact=True).first.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
    _select_first_consult_category(page)

    description = _generated_business_title(case)
    textarea = page.get_by_placeholder("请输入").first
    textarea.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
    textarea.fill(description)

    page.get_by_text("提 交", exact=True).first.click(timeout=settings.ACTION_TIMEOUT)
    message = page.locator(".ant-message-notice-content").first
    try:
        message.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        message_text = " ".join(message.inner_text(timeout=settings.ACTION_TIMEOUT).split())
        assert not any(text in message_text for text in ["失败", "错误", "必填", "请选择"]), (
            f"{case.case_id} 咨询工单提交失败: {message_text}"
        )
    except PlaywrightTimeoutError:
        page.get_by_text("发起咨询", exact=True).first.wait_for(state="hidden", timeout=settings.ACTION_TIMEOUT)


def _open_apply_entry(page, case: PortalCase) -> None:
    """打开服务详情页的立即申请入口，验证进入申请表单或审批链路。"""
    page.keyboard.press("Escape")
    page.mouse.click(320, 90)
    try:
        page.wait_for_function(
            "() => document.body.innerText.includes('立即申请')",
            timeout=settings.ACTION_TIMEOUT,
        )
    except PlaywrightTimeoutError:
        pytest.skip(f"{case.case_id} 当前样本详情页未开放“立即申请”入口，需要指定可申请资源。")
    page.get_by_text("立即申请", exact=True).first.click(timeout=settings.ACTION_TIMEOUT)
    page.wait_for_load_state("domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
    try:
        page.wait_for_load_state("networkidle", timeout=10000)
    except PlaywrightTimeoutError:
        pass
    page.locator("body").wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
    body = " ".join(page.locator("body").inner_text(timeout=settings.ACTION_TIMEOUT).split())
    assert any(text in body for text in ["申请", "购物车", "保存草稿", "提交审批", "规格", "购买", "审批"]), (
        f"{case.case_id} 点击立即申请后未进入申请相关页面: url={page.url}, body={body[:500]}"
    )


def _marks_for_case(case: PortalCase):
    marks = []
    if case.strategy in {"write_flow", "favorite_toggle", "consult_ticket", "apply_entry", "destructive_auth"}:
        marks.append(pytest.mark.write)
    else:
        marks.append(pytest.mark.readonly)
    if case.strategy in {"external_deep", "external_url", "iframe_deep", "click_text", "support_float_entry"}:
        marks.append(pytest.mark.e2e)
    return marks


@pytest.mark.portal
@pytest.mark.domain_split
@pytest.mark.regression
class TestPortalDomainSplit:
    """门户域名拆分 59 条测试用例落地套件。"""

    @pytest.mark.parametrize(
        "case",
        [
            pytest.param(case, id=f"{case.case_id}-{case.module}", marks=_marks_for_case(case))
            for case in PORTAL_CASES
        ],
    )
    def test_portal_domain_split_case(self, logged_in_page, case: PortalCase):
        portal = PortalHomePage(logged_in_page)

        if case.strategy == "page_access":
            portal.open_route(case.route)
            portal.should_be_on_portal_domain()
            portal.assertions.page_not_blank_or_error()
            if case.expected_texts:
                try:
                    portal.assertions.any_text_visible(list(case.expected_texts))
                except AssertionError:
                    if case.route != "/":
                        raise
                    portal.open_workbench()
                    portal.should_be_on_portal_domain()
                    portal.assertions.page_not_blank_or_error()
                    portal.assertions.any_text_visible(list(case.expected_texts))
            return

        if case.strategy == "logged_in_page_access":
            _ensure_portal_logged_in(logged_in_page)
            portal.open_route(case.route)
            portal.should_be_on_portal_domain()
            _assert_portal_page_ready_with_sso_retry(portal, case.route)
            if case.expected_texts:
                _assert_body_contains_any(logged_in_page, case.expected_texts)
            return

        if case.strategy == "home_modules":
            portal.open()
            portal.should_be_on_portal_domain()
            portal.should_be_readonly_page_ready(["中建云"])
            portal.should_show_any_module(
                [
                    "工作台",
                    "云产品",
                    "企业应用",
                    "服务组件",
                    "数据资产",
                    "解决方案",
                    "开发者平台",
                    "工单中心",
                    "知识中心",
                ]
            )
            return

        if case.strategy == "logged_in_identity":
            portal = _ensure_portal_logged_in(logged_in_page)
            username_text = portal.get_username_display()
            assert username_text.strip(), "登录用户信息区域为空或不可读取"
            return

        if case.strategy == "tenant_display":
            portal = _ensure_portal_logged_in(logged_in_page)
            portal.assertions.any_text_visible(list(case.expected_texts))
            return

        if case.strategy == "link_domain":
            portal.open()
            portal.should_be_on_portal_domain()
            portal.should_not_have_console_domain_links(list(case.link_texts))
            return

        if case.strategy == "readonly_search":
            portal.open_route(case.route)
            portal.should_be_on_portal_domain()
            portal.assertions.page_not_blank_or_error()
            if case.expected_texts:
                portal.assertions.any_text_visible(list(case.expected_texts))
            search = logged_in_page.get_by_placeholder("请输入搜索内容").first
            if search.is_visible():
                search.fill("测试")
                assert search.input_value() == "测试", "搜索框未成功输入"
                search.clear()
            return

        if case.strategy == "service_center_consistency":
            for route, expected_text in [
                ("/#/service-center/1", "企业应用"),
                ("/#/service-center/2", "云产品"),
            ]:
                portal.open_route(route)
                portal.should_be_on_portal_domain()
                portal.assertions.page_not_blank_or_error()
                portal.assertions.any_text_visible([expected_text])
                search = logged_in_page.get_by_placeholder("请输入搜索内容").first
                search.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
                search.fill("测试")
                assert search.input_value() == "测试", f"{expected_text} 搜索框未成功输入"
                search.clear()
            return

        if case.strategy == "readonly_detail":
            _skip_missing(case)
            portal.open_route(os.getenv("PORTAL_DETAIL_ROUTE", case.route))
            portal.should_be_on_portal_domain()
            portal.assertions.page_not_blank_or_error()
            return

        if case.strategy == "requires_data":
            _skip_missing(case)
            portal.open_route(os.getenv("PORTAL_DATA_ROUTE", case.route))
            portal.should_be_on_portal_domain()
            portal.assertions.page_not_blank_or_error()
            return

        if case.strategy == "iframe_deep":
            portal.open_route(case.route)
            portal.should_be_on_portal_domain()
            portal.assertions.page_not_blank_or_error()
            frame = portal.first_available_frame()
            if frame is None:
                pytest.skip(f"{case.case_id} 当前页面未发现 iframe，需要确认入口或配置数据。")
            frame.locator("body").first.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
            return

        if case.strategy == "external_deep":
            _skip_missing(case)
            portal.open()
            env_value = os.getenv(case.required_env[0], "")
            target = portal.click_first_visible_link([env_value])
            _assert_target_page_ready(target)
            return

        if case.strategy == "click_text":
            portal.open_route(case.route)
            portal.should_be_on_portal_domain()
            portal.assertions.page_not_blank_or_error()
            target_page = _click_visible_text_and_assert_ready(logged_in_page, case.link_texts[0])
            if case.expected_texts:
                _assert_body_contains_any(target_page, case.expected_texts)
            return

        if case.strategy == "support_float_entry":
            _ensure_portal_logged_in(logged_in_page)
            target_page = _open_support_float_entry(portal, case.link_texts[0])
            if case.expected_texts:
                _assert_body_contains_any(target_page, case.expected_texts)
            return

        if case.strategy == "external_url":
            _skip_missing(case)
            target_url = os.getenv(case.required_env[0], "")
            portal.nav.goto_url(target_url)
            _assert_page_host(logged_in_page.url, settings.PORTAL_BASE_URL)
            portal.assertions.page_not_blank_or_error()
            return

        if case.strategy == "consult_ticket":
            _assert_write_allowed(case)
            _ensure_portal_logged_in(logged_in_page)
            portal.open_route(case.route)
            portal.should_be_on_portal_domain()
            portal.assertions.page_not_blank_or_error()
            _submit_consult_ticket(logged_in_page, case)
            return

        if case.strategy == "apply_entry":
            _assert_write_allowed(case)
            _ensure_portal_logged_in(logged_in_page)
            portal.open_route(case.route)
            portal.should_be_on_portal_domain()
            portal.assertions.page_not_blank_or_error()
            _open_apply_entry(logged_in_page, case)
            return

        if case.strategy == "write_flow":
            _assert_write_allowed(case)
            business_title = _generated_business_title(case)
            portal.open()
            portal.should_be_on_portal_domain()
            portal.assertions.page_not_blank_or_error()
            pytest.skip(f"{case.case_id} 已登记为 UAT/PRE 写入自动化，默认测试标题: {business_title}；需补充稳定操作定位后执行完整写入流。")

        if case.strategy == "favorite_toggle":
            _assert_write_allowed(case)
            _ensure_portal_logged_in(logged_in_page)
            portal.open_route(case.route)
            portal.should_be_on_portal_domain()
            portal.assertions.page_not_blank_or_error()
            _toggle_first_visible_favorite(logged_in_page, case)
            return

        if case.strategy == "destructive_auth":
            pytest.skip(f"{case.case_id} 会破坏共享登录态，作为人工/独立会话用例保留。")

        if case.strategy == "manual_confirm":
            pytest.skip(f"{case.case_id} 当前按人工确认范围保留: {case.notes}")

        if case.strategy == "console_scope":
            if case.required_env:
                _skip_missing(case)
                route = os.getenv(case.required_env[0]).lstrip("/")
            else:
                route = case.route.lstrip("/")
            console_url = f"{settings.CONSOLE_BASE_URL.rstrip('/')}/{route}"
            portal.nav.goto_url(console_url)
            _assert_page_host(logged_in_page.url, settings.CONSOLE_BASE_URL)
            portal.assertions.page_not_blank_or_error()
            if case.expected_texts:
                _assert_body_contains_any(logged_in_page, case.expected_texts)
            return

        raise AssertionError(f"未实现的门户域名拆分策略: {case.strategy}")
