"""Global pytest fixtures for CSCEC UI automation."""

from __future__ import annotations

from collections.abc import Callable
import json
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import pytest
from playwright.sync_api import Browser, BrowserContext, Page

from config.environments import EXTRA_AUTH_ENTRY_URLS
from config.settings import settings
from core.browser_health import BrowserHealthMonitor
from core.execution_contract import PrerequisiteResult
from core.logger import get_logger
from pages.console.console_home_page import ConsoleHomePage
from pages.portal.login_page import LoginPage
from pages.portal.portal_home_page import PortalHomePage
from utils.data_loader import data_loader


logger = get_logger("conftest")


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--refresh-auth",
        action="store_true",
        default=False,
        help="Force login and rewrite auth_states/<env>.json before tests need a logged-in page.",
    )


@pytest.fixture(scope="session")
def settings_fixture():
    logger.info(f"ENV={settings.ENV}({settings.env_label}) BASE_URL={settings.BASE_URL}")
    return settings


@pytest.fixture(scope="session")
def test_data():
    return data_loader


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    launch_args = dict(browser_type_launch_args)
    launch_args["headless"] = settings.HEADLESS
    if settings.SLOW_MO > 0:
        launch_args["slow_mo"] = settings.SLOW_MO
    if settings.BROWSER_CHANNEL:
        launch_args["channel"] = settings.BROWSER_CHANNEL
    return launch_args


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args, browser: Browser, request: pytest.FixtureRequest):
    args = dict(browser_context_args)
    args.update(
        viewport=settings.VIEWPORT,
        ignore_https_errors=True,
        storage_state=str(_ensure_auth_state(browser, request)),
    )
    return args


@pytest.fixture(scope="function")
def logged_in_page(page: Page) -> Page:
    _configure_page_timeouts(page)
    return page


@pytest.fixture(scope="function")
def fresh_context(browser: Browser) -> BrowserContext:
    context = browser.new_context(viewport=settings.VIEWPORT, ignore_https_errors=True)
    context.set_default_timeout(settings.DEFAULT_TIMEOUT)
    context.set_default_navigation_timeout(settings.NAVIGATION_TIMEOUT)
    yield context
    context.close()


@pytest.fixture(scope="function")
def fresh_page(fresh_context: BrowserContext) -> Page:
    page = fresh_context.new_page()
    _configure_page_timeouts(page)
    yield page
    page.close()


@pytest.fixture(scope="function")
def login_page(fresh_page: Page):
    return LoginPage(fresh_page)


@pytest.fixture(scope="function")
def portal_home_page(logged_in_page: Page):
    return PortalHomePage(logged_in_page)


@pytest.fixture(scope="function")
def console_home_page(logged_in_page: Page):
    return ConsoleHomePage(logged_in_page)


@pytest.fixture(scope="function")
def require_case_prerequisite() -> Callable[..., None]:
    """Convert a declared Conditional prerequisite miss into structured N/A."""
    from core.execution_contract import (
        CaseContractRegistry,
        ConditionalNotApplicable,
    )

    registry = CaseContractRegistry.load()

    def require(
        case_id: str,
        result: PrerequisiteResult,
        *,
        health_monitor: BrowserHealthMonitor | None = None,
    ) -> None:
        contract = registry.require(case_id)
        try:
            result.require_for(contract)
        except ConditionalNotApplicable as exc:
            if health_monitor is not None:
                health_monitor.stop().assert_healthy()
            pytest.skip(f"NOT_APPLICABLE[{case_id}][{exc}]")

    return require


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)
    if report.when == "call" and report.failed:
        _capture_failure_screenshot(item)


def pytest_configure(config):
    settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    (settings.REPORTS_DIR / "allure-results").mkdir(parents=True, exist_ok=True)
    logger.info(f"[pytest] reports dir: {settings.REPORTS_DIR}")


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(pytest.mark.slow)


def pytest_runtest_setup(item):
    logger.info(f"[Start] {item.nodeid}")


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    passed = len(terminalreporter.stats.get("passed", []))
    failed = len(terminalreporter.stats.get("failed", []))
    skipped = len(terminalreporter.stats.get("skipped", []))

    terminalreporter.write_sep("=", "Test summary")
    terminalreporter.write_line(f"passed: {passed}")
    terminalreporter.write_line(f"failed: {failed}")
    terminalreporter.write_line(f"skipped: {skipped}")
    terminalreporter.write_line(f"env: {settings.ENV}({settings.env_label})")

    contract_summary = _build_contract_summary(terminalreporter)
    if contract_summary["total"]:
        terminalreporter.write_sep("-", "Production console contract summary")
        for classification, counts in contract_summary["classifications"].items():
            terminalreporter.write_line(
                f"{classification}: passed={counts['passed']} failed={counts['failed']} "
                f"not_applicable={counts['not_applicable']} skipped={counts['skipped']}"
            )
        summary_path = settings.REPORTS_DIR / "prod-console-contract-summary.json"
        summary_path.write_text(
            json.dumps(contract_summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        terminalreporter.write_line(f"contract report: {summary_path}")


def _build_contract_summary(terminalreporter) -> dict:
    """Build execution-responsibility counts from final pytest reports."""
    marker_by_classification = {
        "mandatory": "prod_mandatory",
        "conditional": "prod_conditional",
        "probe": "prod_probe",
        "controlled_write": "controlled_write",
    }
    reports = []
    for outcome in ("passed", "failed", "skipped"):
        reports.extend(terminalreporter.stats.get(outcome, []))

    final_by_node = {}
    outcome_priority = {"passed": 1, "skipped": 2, "failed": 3}
    for report in reports:
        if report.when not in {"setup", "call", "teardown"}:
            continue
        previous = final_by_node.get(report.nodeid)
        if (
            previous is None
            or outcome_priority[report.outcome]
            > outcome_priority[previous.outcome]
        ):
            final_by_node[report.nodeid] = report

    classifications = {}
    total = 0
    for classification, marker in marker_by_classification.items():
        counts = {"passed": 0, "failed": 0, "not_applicable": 0, "skipped": 0}
        for report in final_by_node.values():
            if marker not in report.keywords:
                continue
            total += 1
            if report.outcome == "skipped" and "NOT_APPLICABLE[" in str(report.longrepr):
                counts["not_applicable"] += 1
            else:
                counts[report.outcome] += 1
        classifications[classification] = counts

    return {
        "environment": settings.ENV,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": total,
        "classifications": classifications,
    }


def _configure_page_timeouts(page: Page) -> None:
    page.set_default_timeout(settings.DEFAULT_TIMEOUT)
    page.set_default_navigation_timeout(settings.NAVIGATION_TIMEOUT)


def _auth_state_has_content(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return bool(data.get("cookies") or data.get("origins"))


def _ensure_auth_state(browser: Browser, request: pytest.FixtureRequest) -> Path:
    auth_file = settings.auth_state_file
    refresh = request.config.getoption("--refresh-auth")

    if not refresh and _auth_state_has_content(auth_file) and _looks_authenticated(browser, auth_file):
        logger.info(f"[Auth] reuse {auth_file}")
        return auth_file

    if not refresh and sys.stdin.isatty():
        answer = input(f"Auth state for {settings.ENV} is missing or stale. Refresh now? [y/N] ").strip().lower()
        refresh = answer in {"y", "yes"}

    if not refresh:
        pytest.exit(
            f"Auth state for {settings.ENV} is missing or stale. "
            f"Run: python run_tests.py --env {settings.ENV} --refresh-auth -m smoke",
            returncode=4,
        )

    _perform_login(browser, auth_file)
    return auth_file


def _looks_authenticated(browser: Browser, auth_file: Path) -> bool:
    context = browser.new_context(
        viewport=settings.VIEWPORT,
        ignore_https_errors=True,
        storage_state=str(auth_file),
    )
    context.set_default_timeout(settings.DEFAULT_TIMEOUT)
    context.set_default_navigation_timeout(settings.NAVIGATION_TIMEOUT)
    page = context.new_page()
    try:
        page.goto(settings.BASE_URL, timeout=settings.NAVIGATION_TIMEOUT, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        url = page.url.lower()
        portal_host = urlparse(settings.BASE_URL).netloc.lower()
        parsed = urlparse(url)
        login_like = _is_login_like_url(url)
        if parsed.netloc.lower() != portal_host or login_like:
            return False

        try:
            page.wait_for_function(
                "() => !!window.localStorage.getItem('__login_info__')",
                timeout=10000,
            )
        except Exception:
            return False

        try:
            page.get_by_text("登录", exact=True).first.wait_for(state="visible", timeout=1500)
            return False
        except Exception:
            pass

        # 门户域同样必须有效：跨域 SSO 不生效，门户首页、移动端
        # （cloud-*/udpweb/mobile）与 data 子域都依赖独立的门户会话。
        # 这里只判定「是否被重定向到登录页」这一明确失败信号，
        # 避免因门户首页没有 __login_info__ 而误判。
        portal = (settings.PORTAL_BASE_URL or "").strip()
        if not portal:
            return True
        try:
            page.goto(portal, timeout=settings.NAVIGATION_TIMEOUT, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            portal_url = page.url.lower()
            if _is_login_like_url(portal_url) or "idaas" in portal_url or "/cas/login" in portal_url:
                logger.warning(
                    f"[Auth] portal domain not authenticated, redirect={page.url[:140]}"
                )
                return False
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[Auth] portal state check failed: {exc}")
            return False
    except Exception as exc:
        logger.warning(f"[Auth] state check failed: {exc}")
        return False
    finally:
        context.close()


def _perform_login(browser: Browser, auth_file: Path) -> None:
    """建立并保存登录态，覆盖控制台域与门户域。

    为什么必须登录两个域（2026-11-13 生产实测）：
      控制台（irp-*）与门户（cloud-*）的会话互相独立，跨域 SSO 不生效。
      只登控制台时，`auth_states/<env>.json` 的 origins 只有 irp 域，
      导致门户侧的移动端页面（cloud-*/udpweb/mobile）被重定向到
      idaas 登录页，data 子域返回 code=1401 已退出登录。
      生产回归因此有 6 条用例在「没进入产品」的状态下失败。

    门户登录走与手工一致的黑盒路径（IDaaS -> 其它登录方式 -> 4A 认证图标 ->
    CAS 密码登录），由 LoginPage.login_portal() 实现。
    """
    auth_file.parent.mkdir(parents=True, exist_ok=True)
    context = browser.new_context(viewport=settings.VIEWPORT, ignore_https_errors=True)
    context.set_default_timeout(settings.DEFAULT_TIMEOUT)
    context.set_default_navigation_timeout(settings.NAVIGATION_TIMEOUT)
    page = context.new_page()
    try:
        login = LoginPage(page)

        # 1) 控制台域（irp-*）：控制台类用例依赖
        login.login(password=settings.effective_password).should_login_succeed()
        logger.info("[Auth] console domain logged in")

        # 2) 门户域（cloud-*）：门户/移动端/data 子域依赖。
        #    失败不阻塞整体登录（控制台用例仍可跑），但会明确告警，
        #    避免再次出现「用例失败但看不出是登录态缺失」的情况。
        try:
            login.login_portal()
            logger.info("[Auth] portal domain logged in")
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "[Auth] portal login failed; portal/mobile/data cases will be "
                f"blocked by missing session: {type(exc).__name__}: {exc}"
            )

        # 3) 额外站点（独立 SSO 子域）：访问一次即完成会话建立。
        #    实测 prod 的 data.cscec.com 会自动跳到自己域的工作台并写入
        #    __login_info__；不访问则「数据源配置」入口的接口返回 code=1401。
        for entry in EXTRA_AUTH_ENTRY_URLS.get(settings.ENV, []):
            try:
                page.goto(entry, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(1500)
                logger.info(f"[Auth] extra entry warmed: {entry} -> {page.url[:100]}")
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[Auth] extra entry failed ({entry}): {exc}")

        context.storage_state(path=str(auth_file))
        logger.info(f"[Auth] wrote {auth_file}")
    finally:
        context.close()

    if not _looks_authenticated(browser, auth_file):
        raise AssertionError(f"Login finished but auth state is not valid for {settings.ENV}: {auth_file}")


@pytest.fixture(scope="session")
def auth_state_path(browser: Browser, request: pytest.FixtureRequest) -> Path:
    """统一的登录态文件路径（控制台域 + 门户域都已登录）。

    任何需要「已登录上下文」的模块（含移动端）都应依赖本 fixture，
    而不是直接读 settings.auth_state_file —— 否则 --refresh-auth 不会生效，
    且可能拿到只含控制台域的旧登录态。
    """
    return _ensure_auth_state(browser, request)


def _page_from_funcargs(funcargs: dict) -> Page | None:
    for name in ("page", "logged_in_page", "fresh_page"):
        value = funcargs.get(name)
        if isinstance(value, Page):
            return value

    for value in funcargs.values():
        page = getattr(value, "page", None)
        if isinstance(page, Page):
            return page
    return None


def _capture_failure_screenshot(item) -> None:
    page = _page_from_funcargs(item.funcargs)
    if page is None:
        return

    test_name = item.nodeid.replace("::", "_").replace("/", "_").replace("\\", "_")
    screenshot_path = settings.SCREENSHOTS_DIR / f"FAIL_{test_name}.png"
    try:
        settings.SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_path), full_page=True)
        logger.info(f"[Failure screenshot] {screenshot_path}")
    except Exception as exc:
        logger.warning(f"[Failure screenshot] failed: {exc}")


def _is_login_like_url(url: str) -> bool:
    parsed = urlparse(url.lower())
    return (
        ("iam" in parsed.netloc and "cas" in parsed.path)
        or "passport" in parsed.netloc
        or "/login" in parsed.path
    )
