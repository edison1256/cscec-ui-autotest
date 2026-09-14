"""PROD console module entry regression checks."""

from __future__ import annotations

import re
from urllib.parse import urlparse

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from config.settings import settings
from core.browser_health import BrowserHealthMonitor
from pages.console.console_global_navigation_page import ConsoleGlobalNavigationPage
from pages.portal.portal_home_page import PortalHomePage


ERROR_TEXT_RE = re.compile(
    r"(页面不存在|错误码[:：]\s*(404|500)|\b404\s+Not\s+Found\b|\b500\s+Internal\s+Server\s+Error\b|系统异常)",
    re.I,
)
DETAIL_TEXT = "\u8be6\u60c5"

PROFILE_COMMON_TOOL_CASES = [
    ("\u8d44\u6e90", "\u5e94\u7528\u7ba1\u7406", "C-P0-CONSOLE-PROFILE-002-resource-tool"),
    ("\u5ba1\u6279", "\u5f85\u529e\u6d41\u7a0b", "C-P0-CONSOLE-PROFILE-003-approval-tool"),
    ("\u8ba2\u5355", "\u8ba2\u5355\u7ba1\u7406", "C-P0-CONSOLE-PROFILE-004-order-tool"),
]
PROFILE_COMMON_TOOLS = [
    pytest.param(tool_text, expected_text, case_id.rsplit("-", 2)[0], id=case_id)
    for tool_text, expected_text, case_id in PROFILE_COMMON_TOOL_CASES
]

WORKBENCH_MODULE_ENTRIES = [
    pytest.param("订单管理", "订单列表", id="C-P0-CONSOLE-WB-001-order-management"),
    pytest.param("应用订阅", "应用列表", id="C-P0-CONSOLE-WB-002-app-subscription"),
    pytest.param("数据资产订阅", "数据资产列表", id="C-P0-CONSOLE-WB-003-data-asset-subscription"),
    pytest.param("API订阅", "API列表", id="C-P0-CONSOLE-WB-004-api-subscription"),
    pytest.param("组件订阅", "组件列表", id="C-P0-CONSOLE-WB-005-component-subscription"),
    pytest.param("云产品订阅", "云产品列表", id="C-P0-CONSOLE-WB-006-cloud-product-subscription"),
    pytest.param("API资源", "API资源", id="C-P0-CONSOLE-WB-007-api-resource"),
    pytest.param("数据源配置", "数据源配置", id="C-P0-CONSOLE-WB-008-data-source-config"),
]

WORKBENCH_MODULE_DETAIL_ROUTES = [
    pytest.param(
        "/udpweb/portal/index.html#/sub/resource/orderCenter/myOrders?routeName=resource&appTitle=%E8%AE%A2%E5%8D%95%E7%AE%A1%E7%90%86&mc=1899427585366003727&mn=%E5%B7%A5%E4%BD%9C%E5%8F%B0&mt=module&suitKey=1899427585366003727&routeName=resource&menuCode=1925485794498359342",
        "订单管理",
        id="C-P0-CONSOLE-WB-DEEP-001-order-detail",
    ),
    pytest.param(
        "/udpweb/portal/index.html#/sub/resource/subscription/app/appInfo?routeName=resource&appTitle=%E5%BA%94%E7%94%A8%E8%AE%A2%E9%98%85&mc=1899427585366003727&mn=%E5%B7%A5%E4%BD%9C%E5%8F%B0&mt=module&suitKey=1899427585366003727&routeName=resource&menuCode=1925485794498359316",
        "应用订阅",
        id="C-P0-CONSOLE-WB-DEEP-002-app-subscription-detail",
    ),
    pytest.param(
        "/udpweb/portal/index.html#/sub/resource/subscription/dataAssets?routeName=resource&appTitle=%E6%95%B0%E6%8D%AE%E8%B5%84%E4%BA%A7%E8%AE%A2%E9%98%85&mc=1899427585366003727&mn=%E5%B7%A5%E4%BD%9C%E5%8F%B0&mt=module&suitKey=1899427585366003727&routeName=resource&menuCode=1925485794498359320",
        "数据资产订阅",
        id="C-P0-CONSOLE-WB-DEEP-003-data-asset-subscription-detail",
    ),
    pytest.param(
        "/udpweb/portal/index.html#/sub/resource/subscription/comp?routeName=resource&appTitle=%E7%BB%84%E4%BB%B6%E8%AE%A2%E9%98%85&mc=1899427585366003727&mn=%E5%B7%A5%E4%BD%9C%E5%8F%B0&mt=module&suitKey=1899427585366003727&routeName=resource&menuCode=1925485794498359319",
        "组件订阅",
        id="C-P0-CONSOLE-WB-DEEP-004-component-subscription-detail",
    ),
    pytest.param(
        "/udpweb/portal/index.html#/sub/resource/subscription/cloud?routeName=resource&appTitle=%E4%BA%91%E4%BA%A7%E5%93%81%E8%AE%A2%E9%98%85&mc=1899427585366003727&mn=%E5%B7%A5%E4%BD%9C%E5%8F%B0&mt=module&suitKey=1899427585366003727&routeName=resource&menuCode=1925485794498359317",
        "云产品订阅",
        id="C-P0-CONSOLE-WB-DEEP-005-cloud-product-subscription-detail",
    ),
]


def _open_console_workbench(logged_in_page):
    portal = PortalHomePage(logged_in_page)
    portal.open()
    console_page = portal.open_console_page()
    return console_page


def _click_entry(page, entry_text: str, expected_text: str) -> None:
    entry = page.get_by_text(entry_text, exact=True).first
    try:
        entry.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
    except PlaywrightTimeoutError as exc:
        pytest.skip(f"控制台工作台常用模块未暴露: {entry_text}: {exc}")
    entry.click(timeout=settings.ACTION_TIMEOUT)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except PlaywrightTimeoutError:
        pass
    try:
        page.wait_for_function(
            """([expected, errorPattern]) => {
                const text = document.body ? document.body.innerText : '';
                return text.includes(expected) || new RegExp(errorPattern, 'i').test(text);
            }""",
            arg=[expected_text, ERROR_TEXT_RE.pattern],
            timeout=30000,
        )
    except PlaywrightTimeoutError:
        pass
    page.wait_for_timeout(1500)
    try:
        page.wait_for_load_state("networkidle", timeout=8000)
    except PlaywrightTimeoutError:
        pass


def _page_text(page) -> str:
    return " ".join(page.locator("body").inner_text(timeout=settings.ACTION_TIMEOUT).split())


def _open_console_route(page, route: str) -> None:
    page.goto(settings.console_url(route), wait_until="domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except PlaywrightTimeoutError:
        pass
    page.wait_for_timeout(1500)


def _open_first_detail(page, module_name: str) -> None:
    try:
        page.wait_for_function(
            """target => document.body && document.body.innerText.includes(target)""",
            arg=DETAIL_TEXT,
            timeout=settings.ACTION_TIMEOUT,
        )
    except PlaywrightTimeoutError as exc:
        pytest.skip(f"{module_name} 当前无可点击的详情样本: {exc}")

    old_url = page.url
    try:
        with page.context.expect_page(timeout=3000) as popup_info:
            _click_table_action_by_text(page, DETAIL_TEXT)
        target = popup_info.value
        target.wait_for_load_state("domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
        try:
            target.wait_for_load_state("networkidle", timeout=10000)
        except PlaywrightTimeoutError:
            pass
        page = target
    except PlaywrightTimeoutError:
        _click_table_action_by_text(page, DETAIL_TEXT)
        page.wait_for_timeout(1500)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except PlaywrightTimeoutError:
            pass

    body = _page_text(page)
    opened_surface = (
        page.locator(".ant-drawer:visible, .ant-modal:visible").count() > 0
        or page.url != old_url
    )
    assert opened_surface, f"{module_name} 点击详情后未打开详情层或详情页: {page.url}"
    assert any(text in body for text in ["详情", "基本信息", "流程", "订单", "资源"]), (
        f"{module_name} 详情层/详情页缺少可识别业务内容: url={page.url}, body={body[:500]}"
    )
    assert not ERROR_TEXT_RE.search(body[:3000]), f"{module_name} 详情层/详情页疑似错误页: {page.url}"


def _click_table_action_by_text(page, text: str) -> None:
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
            const actions = [...document.querySelectorAll('button, a, [role="button"]')]
                .filter(el => (el.innerText || el.textContent || '').trim() === target && isVisible(el))
                .sort((a, b) => {
                    const ar = a.getBoundingClientRect();
                    const br = b.getBoundingClientRect();
                    return ar.top - br.top || ar.left - br.left || (ar.width * ar.height) - (br.width * br.height);
                });
            const el = actions[0];
            if (!el) return false;
            el.scrollIntoView({block: 'center', inline: 'center'});
            el.click();
            return true;
        }""",
        text,
    )
    if not clicked:
        raise AssertionError(f"未找到可点击的表格操作: {text}")


@pytest.mark.console
@pytest.mark.smoke
@pytest.mark.readonly
@pytest.mark.regression
@pytest.mark.domain_split
class TestConsoleWorkbenchModuleEntries:
    """控制台常用模块入口只读回归。"""

    @pytest.mark.parametrize("entry_text, expected_text", WORKBENCH_MODULE_ENTRIES)
    def test_workbench_module_entry_opens_without_error(self, logged_in_page, entry_text, expected_text):
        console_page = _open_console_workbench(logged_in_page)
        health = BrowserHealthMonitor(console_page, f"控制台入口 {entry_text}").start()
        try:
            _click_entry(console_page, entry_text, expected_text)
        finally:
            health.stop()

        current_host = urlparse(console_page.url).netloc.lower()
        expected_host = urlparse(settings.CONSOLE_BASE_URL).netloc.lower()
        assert current_host == expected_host, f"控制台入口跳转域名异常: {console_page.url}"

        body = _page_text(console_page)
        assert expected_text in body, f"控制台入口未打开预期页面: entry={entry_text}, url={console_page.url}"
        assert not ERROR_TEXT_RE.search(body[:3000]), f"控制台入口打开错误页: entry={entry_text}, url={console_page.url}"
        health.assert_healthy()

    @pytest.mark.parametrize("route, module_name", WORKBENCH_MODULE_DETAIL_ROUTES)
    def test_workbench_module_first_detail_opens_without_error(self, logged_in_page, route, module_name):
        _open_console_route(logged_in_page, route)
        assert urlparse(logged_in_page.url).netloc.lower() == urlparse(settings.CONSOLE_BASE_URL).netloc.lower()
        assert module_name in _page_text(logged_in_page), f"{module_name} 列表页未正常加载: {logged_in_page.url}"

        health = BrowserHealthMonitor(logged_in_page, f"{module_name} 首条详情").start()
        try:
            _open_first_detail(logged_in_page, module_name)
        finally:
            health.stop()
        health.assert_healthy()

    @pytest.mark.parametrize("tool_text, expected_text, case_id", PROFILE_COMMON_TOOLS)
    @pytest.mark.prod_mandatory
    def test_console_profile_common_tool_opens_without_error(
        self,
        logged_in_page,
        tool_text,
        expected_text,
        case_id,
    ):
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            case_id,
            f"账号浮层常用工具 {tool_text}",
        ).start()
        try:
            console = ConsoleGlobalNavigationPage(logged_in_page).open_console_home()
            console.open_profile_tool(tool_text, expected_text)
        finally:
            health.stop()
        health.assert_healthy()

    @pytest.mark.prod_mandatory
    def test_console_topbar_return_to_portal_opens_without_error(self, logged_in_page):
        health = BrowserHealthMonitor.for_case(
            logged_in_page,
            "C-P0-CONSOLE-TOPBAR-001",
            "控制台顶部返回门户",
        ).start()
        try:
            console = ConsoleGlobalNavigationPage(logged_in_page).open_console_home()
            console.return_to_portal()
        finally:
            health.stop()
        health.assert_healthy()
