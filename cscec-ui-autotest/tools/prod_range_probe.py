"""Read-only production page range probe for domain-split regression candidates.

The probe is intentionally conservative: it opens known cloud/irp/mobile routes,
records HTTP 4xx/5xx responses, and can probe guarded actions by opening their
first dialog/page only. It never clicks final confirmation labels.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import settings


ERROR_TEXT_RE = re.compile(
    r"(页面不存在|错误码[:：]\s*(404|500)|\b404\s+Not\s+Found\b|\b500\s+Internal\s+Server\s+Error\b|系统异常)",
    re.I,
)
SKIP_TEXT_RE = re.compile(
    r"(提交|保存|删除|确认|确定|申请|导入|导出|审批|通过|驳回|撤回|取消|创建|新增|编辑|修改|发布|下架|上架|收藏|分享|退出|登录)",
    re.I,
)
GUARDED_ACTION_RE = re.compile(
    r"(详情|更多|查看|进入|前往|打开|申请|立即申请|编辑|修改|删除|审批|处理|评价|咨询|查询进度|智能客服)",
    re.I,
)
FINAL_CONFIRM_RE = re.compile(
    r"^(确定|确认|是|提交|保存|下一步|完成|通过|驳回|同意|取消订阅|导入|发布|下架|上架)$",
    re.I,
)
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
WRITE_URL_RE = re.compile(
    r"(/delete|/remove|/save|/submit|/approve|/reject|/pass|/cancel|/create|/insert|/update|/edit|/import|/publish|/offline|/online)",
    re.I,
)
CLICK_SELECTOR = "a, button, [role=button], [role=link], [role=tab], [role=menuitem], .ant-tabs-tab"
ACTION_SURFACE_SELECTOR = (
    "a, button, [role=button], [role=link], [role=menuitem], "
    ".ant-btn, .ant-dropdown-menu-item, .ant-table-cell a, .ant-table-cell button"
)
CLOSE_SELECTOR = (
    ".ant-modal-close, .ant-drawer-close, "
    "button:has-text('取消'), button:has-text('关闭'), "
    "[aria-label='Close'], [aria-label='close']"
)


@dataclass
class RouteSpec:
    area: str
    name: str
    url: str
    expected_host: str
    max_clicks: int = 10
    preserve_hash: bool = False


def _url(base: str, path: str = "") -> str:
    if path.startswith(("http://", "https://")):
        return path
    if not path:
        return base.rstrip("/")
    return f"{base.rstrip('/')}/{path.lstrip('/')}"


def _default_routes() -> list[RouteSpec]:
    portal = settings.PORTAL_BASE_URL.rstrip("/")
    console = settings.CONSOLE_BASE_URL.rstrip("/")
    mobile = settings.MOBILE_BASE_URL.rstrip("/")
    portal_host = urlparse(portal).netloc
    console_host = urlparse(console).netloc
    mobile_host = urlparse(mobile).netloc

    routes = [
        RouteSpec("portal", "cloud-home", portal, portal_host),
        RouteSpec("portal", "service-center-enterprise-app", _url(portal, "#/service-center/1"), portal_host),
        RouteSpec("portal", "service-center-cloud-product", _url(portal, "#/service-center/2"), portal_host),
        RouteSpec("portal", "service-center-component", _url(portal, "#/service-center/3"), portal_host),
        RouteSpec("portal", "service-center-data-asset", _url(portal, "#/service-center/4"), portal_host),
        RouteSpec("portal", "solution", _url(portal, "#/solution"), portal_host),
        RouteSpec("portal", "smart-construction", _url(portal, "#/smart-construction"), portal_host),
        RouteSpec("portal", "developer-platform", _url(portal, "#/developer-platform"), portal_host),
        RouteSpec("portal", "support", _url(portal, "#/support"), portal_host),
        RouteSpec(
            "console",
            "console-workbench",
            _url(console, "/udpweb/portal/index.html#/portal/home/workbench?suitKey=portal"),
            console_host,
        ),
        RouteSpec(
            "console-module",
            "workbench-order-management",
            _url(console, "/udpweb/portal/index.html#/sub/resource/orderCenter/myOrders?routeName=resource&appTitle=%E8%AE%A2%E5%8D%95%E7%AE%A1%E7%90%86&mc=1899427585366003727&mn=%E5%B7%A5%E4%BD%9C%E5%8F%B0&mt=module&suitKey=1899427585366003727&routeName=resource&menuCode=1925485794498359342"),
            console_host,
            preserve_hash=True,
        ),
        RouteSpec(
            "console-module",
            "workbench-app-subscription",
            _url(console, "/udpweb/portal/index.html#/sub/resource/subscription/app/appInfo?routeName=resource&appTitle=%E5%BA%94%E7%94%A8%E8%AE%A2%E9%98%85&mc=1899427585366003727&mn=%E5%B7%A5%E4%BD%9C%E5%8F%B0&mt=module&suitKey=1899427585366003727&routeName=resource&menuCode=1925485794498359316"),
            console_host,
            preserve_hash=True,
        ),
        RouteSpec(
            "console-module",
            "workbench-data-asset-subscription",
            _url(console, "/udpweb/portal/index.html#/sub/resource/subscription/dataAssets?routeName=resource&appTitle=%E6%95%B0%E6%8D%AE%E8%B5%84%E4%BA%A7%E8%AE%A2%E9%98%85&mc=1899427585366003727&mn=%E5%B7%A5%E4%BD%9C%E5%8F%B0&mt=module&suitKey=1899427585366003727&routeName=resource&menuCode=1925485794498359320"),
            console_host,
            preserve_hash=True,
        ),
        RouteSpec(
            "console-module",
            "workbench-api-subscription",
            _url(console, "/udpweb/portal/index.html#/sub/resource/subscription/apiResource?routeName=resource&appTitle=API%E8%AE%A2%E9%98%85&mc=1899427585366003727&mn=%E5%B7%A5%E4%BD%9C%E5%8F%B0&mt=module&suitKey=1899427585366003727&routeName=resource&menuCode=1925485794498359318"),
            console_host,
            preserve_hash=True,
        ),
        RouteSpec(
            "console-module",
            "workbench-component-subscription",
            _url(console, "/udpweb/portal/index.html#/sub/resource/subscription/comp?routeName=resource&appTitle=%E7%BB%84%E4%BB%B6%E8%AE%A2%E9%98%85&mc=1899427585366003727&mn=%E5%B7%A5%E4%BD%9C%E5%8F%B0&mt=module&suitKey=1899427585366003727&routeName=resource&menuCode=1925485794498359319"),
            console_host,
            preserve_hash=True,
        ),
        RouteSpec(
            "console-module",
            "workbench-cloud-product-subscription",
            _url(console, "/udpweb/portal/index.html#/sub/resource/subscription/cloud?routeName=resource&appTitle=%E4%BA%91%E4%BA%A7%E5%93%81%E8%AE%A2%E9%98%85&mc=1899427585366003727&mn=%E5%B7%A5%E4%BD%9C%E5%8F%B0&mt=module&suitKey=1899427585366003727&routeName=resource&menuCode=1925485794498359317"),
            console_host,
            preserve_hash=True,
        ),
        RouteSpec(
            "console-module",
            "workbench-api-resource",
            _url(console, "/udpweb/portal/index.html#/sub/resource/resource/apiResource?routeName=resource&appTitle=API%E8%B5%84%E6%BA%90&mc=1899427585366003727&mn=%E5%B7%A5%E4%BD%9C%E5%8F%B0&mt=module&suitKey=1899427585366003727&routeName=resource&menuCode=1925485794498359306"),
            console_host,
            preserve_hash=True,
        ),
        RouteSpec(
            "console-module",
            "workbench-data-source-config",
            _url(console, "/udpweb/portal/index.html#/sub/resource/systemManage/dataSourceManage?routeName=resource&appTitle=%E6%95%B0%E6%8D%AE%E6%BA%90%E9%85%8D%E7%BD%AE&mc=1899427585366003727&mn=%E5%B7%A5%E4%BD%9C%E5%8F%B0&mt=module&suitKey=1899427585366003727&routeName=resource&menuCode=1928020874592694276"),
            console_host,
            preserve_hash=True,
        ),
        RouteSpec(
            "console-module",
            "workbench-subscribed-orders",
            _url(console, "/udpweb/portal/index.html#/sub/resource/orderCenter/subOrders?routeName=resource&appTitle=%E8%A2%AB%E8%AE%A2%E9%98%85%E7%9A%84%E8%AE%A2%E5%8D%95&mc=1899427585366003727&mn=%E5%B7%A5%E4%BD%9C%E5%8F%B0&mt=module&suitKey=1899427585366003727&routeName=resource&menuCode=1980924020313522177"),
            console_host,
            preserve_hash=True,
        ),
        RouteSpec("console", "approval-todo", _url(console, "/udpweb/portal/index.html#/portal/approval/todo"), console_host, preserve_hash=True),
        RouteSpec("console", "order-apply", _url(console, "/udpweb/portal/index.html#/portal/order/apply"), console_host, preserve_hash=True),
        RouteSpec("console", "order-list", _url(console, "/udpweb/portal/index.html#/portal/order/list"), console_host, preserve_hash=True),
        RouteSpec("console", "resource-list", _url(console, "/udpweb/portal/index.html#/portal/resource/list"), console_host, preserve_hash=True),
        RouteSpec("console", "ticket-list", _url(console, "/udpweb/portal/index.html#/portal/ticket/list"), console_host, preserve_hash=True),
        RouteSpec(
            "mobile",
            "mobile-home",
            _url(mobile, "/udpweb/mobile/index.html#/homePage/customize1"),
            mobile_host,
            max_clicks=6,
        ),
        RouteSpec(
            "mobile",
            "mobile-mine",
            _url(mobile, "/udpweb/mobile/index.html#/homePage/mine"),
            mobile_host,
            max_clicks=6,
        ),
    ]
    if settings.DATA_RESOURCE_ROUTE:
        routes.append(RouteSpec("console", "data-resource-management", _url(console, settings.DATA_RESOURCE_ROUTE), console_host, preserve_hash=True))
    if settings.DOC_CENTER_URL:
        routes.append(RouteSpec("portal", "doc-center", settings.DOC_CENTER_URL, urlparse(settings.DOC_CENTER_URL).netloc))
    return routes


def _text_preview(text: str, limit: int = 80) -> str:
    return " ".join(text.split())[:limit]


def _body_status(page) -> dict[str, Any]:
    try:
        body = page.locator("body").inner_text(timeout=5000)
    except Exception as exc:
        return {"blank": True, "error_text": False, "preview": f"<body unavailable: {exc}>"}
    compact = " ".join(body.split())
    return {
        "blank": not bool(compact),
        "error_text": bool(ERROR_TEXT_RE.search(compact[:3000])),
        "preview": compact[:300],
    }


def _hash_preserved(source_url: str, final_url: str) -> bool:
    source_hash = urlparse(source_url).fragment.split("?", 1)[0].rstrip("/")
    if not source_hash:
        return True
    final_hash = urlparse(final_url).fragment.split("?", 1)[0].rstrip("/")
    return final_hash == source_hash


def _collect_clickables(page, max_clicks: int) -> list[dict[str, Any]]:
    items = page.locator(CLICK_SELECTOR).evaluate_all(
        """els => els.map((el, index) => {
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            return {
                index,
                text: (el.innerText || el.textContent || el.getAttribute('title') || el.getAttribute('aria-label') || '').trim(),
                href: el.href || el.getAttribute('href') || '',
                role: el.getAttribute('role') || el.tagName.toLowerCase(),
                visible: rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none',
            };
        })"""
    )
    chosen = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        text = _text_preview(item.get("text") or "")
        href = item.get("href") or ""
        if not item.get("visible") or (not text and not href):
            continue
        if SKIP_TEXT_RE.search(text):
            continue
        key = (text, href)
        if key in seen:
            continue
        seen.add(key)
        item["text"] = text
        chosen.append(item)
        if len(chosen) >= max_clicks:
            break
    return chosen


def _collect_guarded_actions(page, max_actions: int) -> list[dict[str, Any]]:
    items = page.locator(ACTION_SURFACE_SELECTOR).evaluate_all(
        """els => els.map((el, index) => {
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            const text = (el.innerText || el.textContent || el.getAttribute('title') || el.getAttribute('aria-label') || '').trim();
            const disabled = el.disabled || el.getAttribute('aria-disabled') === 'true' || el.className.includes('disabled');
            const inModal = !!el.closest('.ant-modal, .ant-popover, .ant-popconfirm, .ant-drawer');
            return {
                index,
                text,
                href: el.href || el.getAttribute('href') || '',
                role: el.getAttribute('role') || el.tagName.toLowerCase(),
                visible: rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none',
                disabled,
                inModal,
            };
        })"""
    )
    chosen = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        text = _text_preview(item.get("text") or "")
        href = item.get("href") or ""
        if not item.get("visible") or item.get("disabled") or item.get("inModal"):
            continue
        if not text or len(text) > 30 or not GUARDED_ACTION_RE.search(text):
            continue
        if FINAL_CONFIRM_RE.search(text):
            continue
        key = (text, href)
        if key in seen:
            continue
        seen.add(key)
        item["text"] = text
        chosen.append(item)
        if len(chosen) >= max_actions:
            break
    return chosen


def _detect_guard_surface(page) -> dict[str, Any]:
    checks = [
        ("modal", ".ant-modal:visible"),
        ("drawer", ".ant-drawer:visible"),
        ("popover", ".ant-popover:visible, .ant-popconfirm:visible"),
    ]
    for kind, selector in checks:
        try:
            locator = page.locator(selector).last
            if locator.count() > 0 and locator.is_visible(timeout=1000):
                return {"kind": kind, "text": _text_preview(locator.inner_text(timeout=3000), 200)}
        except Exception:
            continue
    return {"kind": "", "text": ""}


def _is_write_request(request) -> bool:
    if request.method not in WRITE_METHODS:
        return False
    return bool(WRITE_URL_RE.search(urlparse(request.url).path))


def _close_guard_surface(page, old_url: str) -> None:
    try:
        close_button = page.locator(CLOSE_SELECTOR).first
        if close_button.count() > 0 and close_button.is_visible(timeout=1000):
            close_button.click(timeout=3000)
            page.wait_for_timeout(500)
            return
    except Exception:
        pass
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(500)
        return
    except Exception:
        pass
    if page.url != old_url:
        try:
            page.go_back(wait_until="domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
            page.wait_for_timeout(500)
        except Exception:
            pass


def _action_locator_by_text(page, text: str):
    candidates = [
        page.locator(f".ant-table-tbody tr:visible a:has-text('{text}')").first,
        page.locator(f".ant-table-tbody tr:visible button:has-text('{text}')").first,
        page.locator(f".ant-table-tbody tr:visible [role=button]:has-text('{text}')").first,
        page.locator(f"a:has-text('{text}')").first,
        page.locator(f"button:has-text('{text}')").first,
        page.locator(f"[role=button]:has-text('{text}')").first,
        page.get_by_text(text, exact=True).first,
    ]
    for locator in candidates:
        try:
            if locator.count() > 0:
                return locator
        except Exception:
            continue
    return page.get_by_text(text, exact=True).first


def _probe_click(context, route: RouteSpec, candidate: dict[str, Any]) -> dict[str, Any]:
    page = context.new_page()
    errors: list[dict[str, Any]] = []
    page.on("response", lambda response: errors.append({"status": response.status, "url": response.url}) if response.status >= 400 else None)
    result: dict[str, Any] = {
        "text": candidate.get("text", ""),
        "href": candidate.get("href", ""),
        "role": candidate.get("role", ""),
        "status": "unknown",
        "final_url": "",
        "errors": [],
        "body": {},
    }
    try:
        page.goto(route.url, wait_until="domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
        page.wait_for_timeout(1000)
        index = int(candidate["index"])
        locator = page.locator(CLICK_SELECTOR).nth(index)
        old_url = page.url
        try:
            with page.context.expect_page(timeout=3000) as popup_info:
                locator.click(timeout=settings.ACTION_TIMEOUT)
            target = popup_info.value
            target.wait_for_load_state("domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
            try:
                target.wait_for_load_state("networkidle", timeout=8000)
            except PlaywrightTimeoutError:
                pass
            result["final_url"] = target.url
            result["body"] = _body_status(target)
            target.close()
        except PlaywrightTimeoutError:
            locator.click(timeout=settings.ACTION_TIMEOUT)
            page.wait_for_timeout(1500)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except PlaywrightTimeoutError:
                pass
            result["final_url"] = page.url
            result["body"] = _body_status(page)
        result["changed"] = result["final_url"] != old_url
        result["errors"] = errors
        bad_responses = [err for err in errors if err["status"] in (404, 500)]
        if bad_responses or result["body"].get("blank") or result["body"].get("error_text"):
            result["status"] = "suspect"
        else:
            result["status"] = "ok"
    except Exception as exc:
        result["status"] = "probe_error"
        result["error"] = str(exc)
        result["errors"] = errors
    finally:
        page.close()
    return result


def _probe_text_click(context, route: RouteSpec, text: str) -> dict[str, Any]:
    page = context.new_page()
    errors: list[dict[str, Any]] = []
    page.on("response", lambda response: errors.append({"status": response.status, "url": response.url}) if response.status >= 400 else None)
    result: dict[str, Any] = {
        "text": text,
        "href": "",
        "role": "text",
        "status": "unknown",
        "final_url": "",
        "errors": [],
        "body": {},
    }
    try:
        page.goto(route.url, wait_until="domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except PlaywrightTimeoutError:
            pass
        locator = _action_locator_by_text(page, text)
        locator.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        old_url = page.url
        try:
            with page.context.expect_page(timeout=3000) as popup_info:
                locator.click(timeout=settings.ACTION_TIMEOUT, force=True)
            target = popup_info.value
            target.wait_for_load_state("domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
            try:
                target.wait_for_load_state("networkidle", timeout=8000)
            except PlaywrightTimeoutError:
                pass
            result["final_url"] = target.url
            result["body"] = _body_status(target)
            target.close()
        except PlaywrightTimeoutError:
            locator.click(timeout=settings.ACTION_TIMEOUT, force=True)
            page.wait_for_timeout(1500)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except PlaywrightTimeoutError:
                pass
            result["final_url"] = page.url
            result["body"] = _body_status(page)
        result["changed"] = result["final_url"] != old_url
        result["errors"] = errors
        bad_responses = [err for err in errors if err["status"] in (404, 500)]
        if bad_responses or result["body"].get("blank") or result["body"].get("error_text"):
            result["status"] = "suspect"
        else:
            result["status"] = "ok"
    except Exception as exc:
        result["status"] = "probe_error"
        result["error"] = str(exc)
        result["errors"] = errors
    finally:
        page.close()
    return result


def _probe_guarded_action(context, route: RouteSpec, candidate: dict[str, Any], settle_ms: int = 3000) -> dict[str, Any]:
    page = context.new_page()
    errors: list[dict[str, Any]] = []
    writes: list[dict[str, Any]] = []
    page.on("response", lambda response: errors.append({"status": response.status, "url": response.url}) if response.status >= 400 else None)
    page.on(
        "request",
        lambda request: writes.append({"method": request.method, "url": request.url})
        if _is_write_request(request)
        else None,
    )
    result: dict[str, Any] = {
        "text": candidate.get("text", ""),
        "href": candidate.get("href", ""),
        "role": candidate.get("role", ""),
        "status": "unknown",
        "final_url": "",
        "errors": [],
        "write_requests": [],
        "guard_surface": {},
        "body": {},
    }
    try:
        page.goto(route.url, wait_until="domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except PlaywrightTimeoutError:
            pass
        page.wait_for_timeout(settle_ms)
        old_url = page.url
        locator = page.locator(ACTION_SURFACE_SELECTOR).nth(int(candidate["index"]))
        errors.clear()
        writes.clear()
        try:
            with page.context.expect_page(timeout=3000) as popup_info:
                locator.click(timeout=settings.ACTION_TIMEOUT)
            target = popup_info.value
            target.wait_for_load_state("domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
            try:
                target.wait_for_load_state("networkidle", timeout=8000)
            except PlaywrightTimeoutError:
                pass
            result["final_url"] = target.url
            result["body"] = _body_status(target)
            target.close()
        except PlaywrightTimeoutError:
            locator.click(timeout=settings.ACTION_TIMEOUT)
            page.wait_for_timeout(1800)
            result["guard_surface"] = _detect_guard_surface(page)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except PlaywrightTimeoutError:
                pass
            result["final_url"] = page.url
            result["body"] = _body_status(page)
            _close_guard_surface(page, old_url)

        result["changed"] = result["final_url"] != old_url
        result["errors"] = errors
        result["write_requests"] = writes
        bad_responses = [err for err in errors if err["status"] in (404, 500)]
        if bad_responses or result["body"].get("blank") or result["body"].get("error_text"):
            result["status"] = "suspect"
        elif writes:
            result["status"] = "write_risk"
        elif result["guard_surface"].get("kind") or result.get("changed"):
            result["status"] = "guarded_ok"
        else:
            result["status"] = "no_effect"
    except Exception as exc:
        result["status"] = "probe_error"
        result["error"] = str(exc)
        result["errors"] = errors
        result["write_requests"] = writes
    finally:
        page.close()
    return result


def _probe_guarded_text(context, route: RouteSpec, text: str, depth: int = 1, settle_ms: int = 3000) -> dict[str, Any]:
    page = context.new_page()
    errors: list[dict[str, Any]] = []
    writes: list[dict[str, Any]] = []
    page.on("response", lambda response: errors.append({"status": response.status, "url": response.url}) if response.status >= 400 else None)
    page.on(
        "request",
        lambda request: writes.append({"method": request.method, "url": request.url})
        if _is_write_request(request)
        else None,
    )
    result: dict[str, Any] = {
        "text": text,
        "href": "",
        "role": "text",
        "status": "unknown",
        "final_url": "",
        "errors": [],
        "write_requests": [],
        "guard_surface": {},
        "body": {},
        "children": [],
    }
    try:
        page.goto(route.url, wait_until="domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except PlaywrightTimeoutError:
            pass
        page.wait_for_timeout(settle_ms)
        locator = _action_locator_by_text(page, text)
        try:
            locator.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        except PlaywrightTimeoutError as exc:
            result["status"] = (
                "route_suspect_action_absent"
                if any(err["status"] in (404, 500) for err in errors) or _body_status(page).get("error_text")
                else "action_absent"
            )
            result["error"] = str(exc)
            result["final_url"] = page.url
            result["body"] = _body_status(page)
            result["errors"] = errors
            result["write_requests"] = writes
            return result
        old_url = page.url
        errors.clear()
        writes.clear()
        try:
            with page.context.expect_page(timeout=3000) as popup_info:
                locator.click(timeout=settings.ACTION_TIMEOUT, force=True)
            target = popup_info.value
            target.wait_for_load_state("domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
            try:
                target.wait_for_load_state("networkidle", timeout=8000)
            except PlaywrightTimeoutError:
                pass
            result["final_url"] = target.url
            result["body"] = _body_status(target)
            if depth > 1 and not result["body"].get("error_text") and not result["body"].get("blank"):
                result["children"] = _probe_child_actions(target, depth - 1)
            target.close()
        except PlaywrightTimeoutError:
            locator.click(timeout=settings.ACTION_TIMEOUT, force=True)
            page.wait_for_timeout(1800)
            result["guard_surface"] = _detect_guard_surface(page)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except PlaywrightTimeoutError:
                pass
            result["final_url"] = page.url
            result["body"] = _body_status(page)
            if depth > 1 and page.url != old_url and not result["body"].get("error_text") and not result["body"].get("blank"):
                result["children"] = _probe_child_actions(page, depth - 1)
            _close_guard_surface(page, old_url)

        result["changed"] = result["final_url"] != old_url
        result["errors"] = errors
        result["write_requests"] = writes
        bad_responses = [err for err in errors if err["status"] in (404, 500)]
        child_suspect = any(child.get("status") not in {"guarded_ok", "ok"} for child in result.get("children", []))
        if bad_responses or result["body"].get("blank") or result["body"].get("error_text") or child_suspect:
            result["status"] = "suspect"
        elif writes:
            result["status"] = "write_risk"
        elif result["guard_surface"].get("kind") or result.get("changed"):
            result["status"] = "guarded_ok"
        else:
            result["status"] = "no_effect"
    except Exception as exc:
        result["status"] = "probe_error"
        result["error"] = str(exc)
        result["errors"] = errors
        result["write_requests"] = writes
    finally:
        page.close()
    return result


def _probe_child_actions(page, depth: int) -> list[dict[str, Any]]:
    actions = _collect_guarded_actions(page, 5)
    results = []
    for action in actions:
        text = action.get("text", "")
        if not text or FINAL_CONFIRM_RE.search(text):
            continue
        old_url = page.url
        errors: list[dict[str, Any]] = []
        writes: list[dict[str, Any]] = []
        page.on("response", lambda response: errors.append({"status": response.status, "url": response.url}) if response.status >= 400 else None)
        page.on(
            "request",
            lambda request: writes.append({"method": request.method, "url": request.url})
            if _is_write_request(request)
            else None,
        )
        child = {
            "text": text,
            "status": "unknown",
            "final_url": "",
            "errors": [],
            "write_requests": [],
            "guard_surface": {},
            "body": {},
        }
        try:
            _action_locator_by_text(page, text).click(timeout=settings.ACTION_TIMEOUT, force=True)
            page.wait_for_timeout(1500)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except PlaywrightTimeoutError:
                pass
            child["final_url"] = page.url
            child["guard_surface"] = _detect_guard_surface(page)
            child["body"] = _body_status(page)
            child["errors"] = errors
            child["write_requests"] = writes
            if any(err["status"] in (404, 500) for err in errors) or child["body"].get("blank") or child["body"].get("error_text"):
                child["status"] = "suspect"
            elif writes:
                child["status"] = "write_risk"
            elif child["guard_surface"].get("kind") or page.url != old_url:
                child["status"] = "guarded_ok"
            else:
                child["status"] = "no_effect"
        except Exception as exc:
            child["status"] = "probe_error"
            child["error"] = str(exc)
        finally:
            _close_guard_surface(page, old_url)
        results.append(child)
        if len(results) >= 5 or depth <= 0:
            break
    return results


def probe(
    routes: list[RouteSpec],
    click: bool,
    click_limit: int | None = None,
    click_texts: list[str] | None = None,
    guarded_texts: list[str] | None = None,
    guarded_actions: bool = False,
    guarded_limit: int = 5,
    deep_depth: int = 1,
    settle_ms: int = 3000,
) -> dict[str, Any]:
    output: dict[str, Any] = {
        "env": settings.ENV,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "base_urls": {
            "portal": settings.PORTAL_BASE_URL,
            "console": settings.CONSOLE_BASE_URL,
            "mobile": settings.MOBILE_BASE_URL,
        },
        "routes": [],
    }
    with sync_playwright() as pw:
        launch_args = {"headless": settings.HEADLESS}
        browser_type = pw.chromium
        browser = browser_type.launch(channel=settings.BROWSER_CHANNEL or None, **launch_args)
        context = browser.new_context(
            viewport=settings.VIEWPORT,
            ignore_https_errors=True,
            storage_state=str(settings.auth_state_file),
        )
        context.set_default_timeout(settings.DEFAULT_TIMEOUT)
        context.set_default_navigation_timeout(settings.NAVIGATION_TIMEOUT)
        try:
            for route in routes:
                print(f"[probe] {route.area}/{route.name} {route.url}", flush=True)
                route_result: dict[str, Any] = asdict(route)
                route_result["network_errors"] = []
                page = context.new_page()
                page.on(
                    "response",
                    lambda response, bucket=route_result["network_errors"]: bucket.append(
                        {"status": response.status, "url": response.url}
                    )
                    if response.status >= 400
                    else None,
                )
                try:
                    page.goto(route.url, wait_until="domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
                    try:
                        page.wait_for_load_state("networkidle", timeout=10000)
                    except PlaywrightTimeoutError:
                        pass
                    page.wait_for_timeout(settle_ms)
                    route_result["final_url"] = page.url
                    route_result["host_ok"] = urlparse(page.url).netloc.lower() == route.expected_host.lower()
                    route_result["hash_preserved"] = _hash_preserved(route.url, page.url) if route.preserve_hash else True
                    route_result["body"] = _body_status(page)
                    route_result["clickables"] = _collect_clickables(page, route.max_clicks)
                    route_result["guarded_actions"] = _collect_guarded_actions(page, guarded_limit) if guarded_actions else []
                    route_result["status"] = "suspect" if (
                        not route_result["host_ok"]
                        or not route_result["hash_preserved"]
                        or route_result["body"].get("blank")
                        or route_result["body"].get("error_text")
                        or any(err["status"] in (404, 500) for err in route_result["network_errors"])
                    ) else "ok"
                except Exception as exc:
                    route_result["status"] = "probe_error"
                    route_result["error"] = str(exc)
                    route_result["clickables"] = []
                finally:
                    page.close()

                if click and route_result.get("clickables"):
                    candidates = route_result["clickables"]
                    if click_limit is not None:
                        candidates = candidates[:click_limit]
                    route_result["click_results"] = []
                    for candidate in candidates:
                        label = candidate.get("text") or candidate.get("href") or candidate.get("role")
                        print(f"[click] {route.name}: {label}", flush=True)
                        route_result["click_results"].append(_probe_click(context, route, candidate))
                if click_texts:
                    route_result.setdefault("click_results", [])
                    for text in click_texts:
                        if SKIP_TEXT_RE.search(text):
                            continue
                        print(f"[click-text] {route.name}: {text}", flush=True)
                        route_result["click_results"].append(_probe_text_click(context, route, text))
                if guarded_actions and route_result.get("guarded_actions"):
                    route_result.setdefault("guarded_action_results", [])
                    for candidate in route_result["guarded_actions"]:
                        label = candidate.get("text") or candidate.get("href") or candidate.get("role")
                        print(f"[guarded] {route.name}: {label}", flush=True)
                        route_result["guarded_action_results"].append(
                            _probe_guarded_action(context, route, candidate, settle_ms=settle_ms)
                        )
                if guarded_texts:
                    route_result.setdefault("guarded_action_results", [])
                    for text in guarded_texts:
                        if FINAL_CONFIRM_RE.search(text):
                            continue
                        print(f"[guarded-text] {route.name}: {text}", flush=True)
                        route_result["guarded_action_results"].append(
                            _probe_guarded_text(context, route, text, depth=deep_depth, settle_ms=settle_ms)
                        )
                output["routes"].append(route_result)
        finally:
            context.close()
            browser.close()
    output["finished_at"] = datetime.now().isoformat(timespec="seconds")
    return output


def _write_markdown(data: dict[str, Any], path: Path) -> None:
    lines = [
        "# 生产域名拆分扩展探查报告",
        "",
        f"- 环境: {data['env']}",
        f"- 开始时间: {data['started_at']}",
        f"- 结束时间: {data.get('finished_at', '')}",
        f"- portal: {data['base_urls']['portal']}",
        f"- console: {data['base_urls']['console']}",
        f"- mobile: {data['base_urls']['mobile']}",
        "",
        "## 异常/疑似异常",
        "",
    ]
    suspect_count = 0
    for route in data["routes"]:
        click_suspects = [item for item in route.get("click_results", []) if item.get("status") != "ok"]
        guarded_suspects = [
            item
            for item in route.get("guarded_action_results", [])
            if item.get("status") not in {"guarded_ok", "ok", "action_absent"}
        ]
        route_suspect = route.get("status") != "ok"
        if not route_suspect and not click_suspects and not guarded_suspects:
            continue
        suspect_count += 1
        lines.append(f"### {route['area']} / {route['name']}")
        lines.append(f"- URL: {route['url']}")
        lines.append(f"- 页面状态: {route.get('status')}，最终地址: {route.get('final_url', '')}")
        if route.get("preserve_hash"):
            lines.append(f"- 深链保持: {route.get('hash_preserved')}")
        lines.append(f"- 页面摘要: {route.get('body', {}).get('preview', '')}")
        bad = [err for err in route.get("network_errors", []) if err["status"] in (404, 500)]
        if bad:
            lines.append("- 页面加载异常响应:")
            for err in bad[:10]:
                lines.append(f"  - {err['status']} {err['url']}")
        if click_suspects:
            lines.append("- 点击后疑似异常:")
            for item in click_suspects:
                lines.append(f"  - `{item.get('text') or item.get('href')}` -> {item.get('status')} -> {item.get('final_url')}")
                for err in [err for err in item.get("errors", []) if err["status"] in (404, 500)][:5]:
                    lines.append(f"    - {err['status']} {err['url']}")
        if guarded_suspects:
            lines.append("- 受保护动作疑似异常:")
            for item in guarded_suspects:
                lines.append(f"  - `{item.get('text') or item.get('href')}` -> {item.get('status')} -> {item.get('final_url')}")
                guard = item.get("guard_surface") or {}
                if guard.get("kind"):
                    lines.append(f"    - guard: {guard.get('kind')} {guard.get('text', '')}")
                for err in [err for err in item.get("errors", []) if err["status"] in (404, 500)][:5]:
                    lines.append(f"    - {err['status']} {err['url']}")
                for req in item.get("write_requests", [])[:5]:
                    lines.append(f"    - write-risk {req['method']} {req['url']}")
        lines.append("")
    if suspect_count == 0:
        lines.append("未发现页面级或点击级 404/500/空白页疑似异常。")
        lines.append("")

    lines.extend(["## 覆盖摘要", ""])
    for route in data["routes"]:
        lines.append(
            f"- {route['area']} / {route['name']}: {route.get('status')}，"
            f"可点击候选 {len(route.get('clickables', []))}，"
            f"点击探查 {len(route.get('click_results', []))}，"
            f"受保护动作 {len(route.get('guarded_action_results', []))}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--click", action="store_true", help="Probe safe navigation-like clicks.")
    parser.add_argument("--only", default="", help="Comma-separated route names or areas to include.")
    parser.add_argument("--limit-routes", type=int, default=0, help="Limit number of routes after filtering.")
    parser.add_argument("--click-limit", type=int, default=3, help="Per-route click probe limit.")
    parser.add_argument("--click-texts", default="", help="Comma-separated visible texts to click on every included route.")
    parser.add_argument("--guarded-actions", action="store_true", help="Probe first-step guarded actions without final confirmation.")
    parser.add_argument("--guarded-limit", type=int, default=5, help="Per-route guarded action probe limit.")
    parser.add_argument("--guarded-texts", default="", help="Comma-separated action texts to probe without final confirmation.")
    parser.add_argument("--deep-depth", type=int, default=1, help="Guarded action depth for pages reached by text actions.")
    parser.add_argument("--settle-ms", type=int, default=3000, help="Extra wait after route load before action discovery.")
    parser.add_argument("--output-dir", default=str(settings.REPORTS_DIR), help="Directory for JSON/Markdown reports.")
    args = parser.parse_args()

    if settings.ENV != "prod":
        raise SystemExit(f"Refusing to run production range probe when ENV={settings.ENV!r}; set ENV=prod.")
    if not settings.auth_state_file.exists():
        raise SystemExit(f"Missing auth state: {settings.auth_state_file}")

    routes = _default_routes()
    if args.only:
        terms = {term.strip() for term in args.only.split(",") if term.strip()}
        routes = [route for route in routes if route.name in terms or route.area in terms]
    if args.limit_routes:
        routes = routes[: args.limit_routes]

    click_texts = [text.strip() for text in args.click_texts.split(",") if text.strip()]
    guarded_texts = [text.strip() for text in args.guarded_texts.split(",") if text.strip()]
    data = probe(
        routes,
        click=args.click,
        click_limit=args.click_limit,
        click_texts=click_texts,
        guarded_texts=guarded_texts,
        guarded_actions=args.guarded_actions,
        guarded_limit=args.guarded_limit,
        deep_depth=args.deep_depth,
        settle_ms=args.settle_ms,
    )
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    json_path = output_dir / f"prod-range-probe-{stamp}.json"
    md_path = output_dir / f"prod-range-probe-{stamp}.md"
    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(data, md_path)
    print(f"JSON={json_path}")
    print(f"MARKDOWN={md_path}")
    suspects = sum(
        1
        for route in data["routes"]
        if route.get("status") != "ok"
        or any(item.get("status") != "ok" for item in route.get("click_results", []))
        or any(item.get("status") not in {"guarded_ok", "ok", "action_absent"} for item in route.get("guarded_action_results", []))
    )
    print(f"ROUTES={len(data['routes'])} SUSPECT_ROUTES={suspects}")
    return 1 if suspects else 0


if __name__ == "__main__":
    raise SystemExit(main())
