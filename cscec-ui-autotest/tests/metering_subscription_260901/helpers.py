"""Shared navigation and assertion helpers for metering-subscription 260901.

All knowledge (routes, anchors, API patterns) verified against PRE on 2026-10-09
via scratch_recon1~7. Read-only interactions only.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from playwright.sync_api import Page, Response, expect

from config.settings import settings

# ---------------------------------------------------------------------------
# Environment constants (PRE)
# ---------------------------------------------------------------------------
PORTAL_ROOT = "https://cloud-pre.cscec.com/"
CONSOLE_ROOT = "https://irp-pre.cscec.com/"
WORKBENCH_URL = (
    "https://cloud-pre.cscec.com/udpweb/portal/index.html"
    "?#/portal/home/workbench?suitKey=1899427585366003727"
    "&mc=1899427585366003727&mn=%E5%B7%A5%E4%BD%9C%E5%8F%B0&mt=module&appTitle=%E5%B7%A5%E4%BD%9C%E5%8F%B0"
)
CONSOLE_URL = (
    "https://irp-pre.cscec.com/udpweb/portal/index.html"
    "?#/portal/home/workbench?suitKey=1899427585366003726"
    "&mc=1899427585366003726&mn=%E6%8E%A7%E5%88%B6%E5%8F%B0&mt=module&appTitle=%E6%8E%A7%E5%88%B6%E5%8F%B0"
)

# API patterns verified in recon
AGGREGATE_WB_PAT = re.compile(r"/irp-api/irp-portal-workbench/quota-instance/aggregate")
AGGREGATE_CS_PAT = re.compile(
    r"/irp-api/irp-portal-console/quota-instance/aggregateForConsole"
)
SUBTABLE_PAT = re.compile(r"quota-instance/listByIds")
ORDER_PAT = re.compile(r"quota-instance-order/findByOrderIds")

# Anchor data verified on PRE (single-account tenant ZH_01_0000_0001_0001)
ANCHOR_RESOURCE_WPS = "WPS服务组件"
ANCHOR_RESOURCE_TAG = "标签中心"
ANCHOR_TENANT_NAME = "技术与大数据平台项目组"
ANCHOR_TENANT_NO = "ZH_01_0000_0001_0001"
ANCHOR_ORDER_ID = "PO2025103015352000"
ANCHOR_APPLY_APP = "一体化资源平台项目"
CS_ANCHOR_RESOURCE = "实际控制人"
CS_ANCHOR_APP = "国资委审计专用"

# Field contracts from the outline (verified against real pages)
PARENT_HEADERS = (
    "序号", "租户编码", "租户名称", "资源名称", "资源编码",
    "服务模式", "资源发布方", "订阅数量", "操作",
)
CHILD_HEADERS = (
    "资源名称", "服务模式", "订阅应用", "资源发布方", "生效时间",
    "截止时间", "可用状态", "总可调用额", "已调用额", "剩余调用额", "操作",
)
ORDER_HEADERS = ("订单ID", "订阅人", "订阅人所在组织", "生效时间", "操作")
QUERY_FIELD_LABELS = ("资源名称", "资源编码", "订阅时间")

SENSITIVE_TOKENS = ("AKSK", "AKSk", "aksk", "SecretKey", "secretKey", "secret_key")

RESULTS_DIR = settings.REPORTS_DIR / "metering260901"


# ---------------------------------------------------------------------------
# CAS login (shared by workbench + console; both IAM domains handled)
# ---------------------------------------------------------------------------
def _fill_cas_field(frame, sel: str, value: str) -> None:
    frame.fill(sel, value)
    time.sleep(0.4)
    actual = frame.eval_on_selector(sel, "e => e.value")
    if actual != value:
        frame.fill(sel, "")
        frame.type(sel, value, delay=40)
        time.sleep(0.3)


def cas_login(page: Page, root: str) -> None:
    """Login the given page via portal/console root. Reuses existing session."""
    page.goto(root, wait_until="domcontentloaded", timeout=60000)
    time.sleep(2.5)
    if page.evaluate("() => !!window.localStorage.getItem('__login_info__')"):
        return
    frame = page.frame(name="qrcont")
    if frame is None:
        for cand in (".login-btn", "a[href*='login']", "text=登录"):
            try:
                page.locator(cand).first.click(timeout=2500)
                break
            except Exception:
                continue
        page.wait_for_selector("#qrcont", timeout=15000)
        frame = page.frame(name="qrcont")
    assert frame is not None, f"CAS login iframe not found for {root}"
    frame.wait_for_selector("#usernameIn", timeout=10000)
    time.sleep(1.0)
    _fill_cas_field(frame, "#usernameIn", settings.USERNAME)
    _fill_cas_field(frame, "#pwdIn", settings.effective_password)
    time.sleep(0.5)
    frame.click("#pwdLoginButton")
    page.wait_for_function(
        "() => !!window.localStorage.getItem('__login_info__')", timeout=30000
    )
    time.sleep(1.5)


def safe_goto(page: Page, url: str, tries: int = 3) -> None:
    for i in range(tries):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)
            return
        except Exception:
            time.sleep(3)
    page.goto(url, wait_until="domcontentloaded", timeout=60000)


# ---------------------------------------------------------------------------
# Click helpers
# ---------------------------------------------------------------------------
def click_when_visible(page: Page, text: str, timeout_ms: int = 10000) -> bool:
    """Click exact text in whatever frame shows it, polling until deadline."""
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        for fr in page.frames:
            try:
                btn = fr.get_by_text(text, exact=True).first
                if btn.is_visible(timeout=600):
                    btn.click()
                    return True
            except Exception:
                continue
        time.sleep(0.4)
    return False


def click_text_strict(page: Page, text: str, timeout_ms: int = 8000) -> bool:
    """Click a visible, non-<title> exact-text element (avoids <title> hits)."""
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        for fr in page.frames:
            try:
                loc = fr.get_by_text(text, exact=True)
                for i in range(min(loc.count(), 8)):
                    el = loc.nth(i)
                    try:
                        if not el.is_visible(timeout=400):
                            continue
                        if (el.evaluate("e => e.tagName") or "").upper() == "TITLE":
                            continue
                        el.click()
                        return True
                    except Exception:
                        continue
            except Exception:
                continue
        time.sleep(0.4)
    return False


def open_menu(page: Page, *titles: str) -> None:
    """Click through menu titles sequentially."""
    for t in titles:
        ok = click_when_visible(page, t, timeout_ms=10000)
        assert ok, f"菜单项不可点击: {t}"
        time.sleep(1.2)


def open_api_subscription_workbench(page: Page) -> Response | None:
    """Workbench: 我的订阅 -> API订阅; returns aggregate API response if captured.

    Always detours through about:blank first: navigating to the same hash URL
    is a same-document no-op in Chromium and would inherit stale page state.
    """
    page.goto("about:blank", wait_until="domcontentloaded", timeout=30000)
    page.goto(WORKBENCH_URL, wait_until="domcontentloaded", timeout=60000)
    time.sleep(2.5)
    response = None
    try:
        with page.expect_response(
            lambda r: bool(AGGREGATE_WB_PAT.search(r.url)), timeout=20000
        ) as resp_info:
            open_menu(page, "我的订阅", "API订阅")
        response = resp_info.value
    except Exception:
        # 页面可能复用已加载 chunk，aggregate 已发完；退化为等待表格渲染
        pass
    wait_list_ready(page)
    return response


def open_api_list_console(page: Page) -> Response | None:
    """Console: 订阅服务 -> API列表; returns aggregateForConsole response."""
    page.goto("about:blank", wait_until="domcontentloaded", timeout=30000)
    page.goto(CONSOLE_URL, wait_until="domcontentloaded", timeout=60000)
    time.sleep(2.5)
    response = None
    try:
        with page.expect_response(
            lambda r: bool(AGGREGATE_CS_PAT.search(r.url)), timeout=20000
        ) as resp_info:
            open_menu(page, "订阅服务", "API列表")
        response = resp_info.value
    except Exception:
        pass
    wait_list_ready(page)
    return response


def wait_list_ready(page: Page, timeout_s: int = 25) -> bool:
    """Wait until the aggregate list table header renders (租户编码 present)."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            if page.get_by_text("租户编码", exact=True).first.is_visible(timeout=800):
                time.sleep(1.0)
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


# ---------------------------------------------------------------------------
# Assertions
# ---------------------------------------------------------------------------
def visible_texts(page: Page, selector: str = "body") -> str:
    """Best-effort full text of the main document."""
    try:
        return page.locator(selector).inner_text(timeout=5000)
    except Exception:
        return ""


def assert_headers_present(page: Page, headers: tuple[str, ...], ctx: str) -> None:
    body = visible_texts(page)
    missing = [h for h in headers if h not in body]
    assert not missing, f"{ctx} 缺失表头/字段: {missing}; 实际文本片段: {body[:400]}"


def expand_first_row(page: Page) -> bool:
    """Click the first 查看 action and wait until the child table renders."""
    if not click_when_visible(page, "查看", timeout_ms=8000):
        return False
    # 稳态等待：子表渲染完成的标志是“查看订单明细”或“收起”出现
    deadline = time.time() + 10
    while time.time() < deadline:
        body = visible_texts(page)
        if "查看订单明细" in body or "收起" in body:
            time.sleep(1.0)
            return True
        time.sleep(0.5)
    return False


def page_contains_any(page: Page, *kws: str) -> tuple[str, ...]:
    body = visible_texts(page)
    return tuple(kw for kw in kws if kw in body)


def gateway_error(page: Page) -> bool:
    """Detect pre-env gateway/micro-app load failures (502/qiankun)."""
    body = visible_texts(page)
    return (
        "502" in body
        and "Bad Gateway" in body
    ) or "You need to export lifecycle functions" in body
