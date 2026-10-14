"""Independent PRE sessions, explicit export opt-in, and per-run evidence."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from playwright.sync_api import expect

from config.settings import settings
from core.metering_blackbox_contract import MissingMeteringData, allowed_request, assert_pre, load_manifest, optional_telemetry
from pages.metering_blackbox_page import MeteringBlackboxPage, visible

logger = logging.getLogger(__name__)


def pytest_addoption(parser):
    parser.addoption("--metering-allow-export", action="store_true", default=False,
                     help="Allow CSV export tasks, not subscription/order mutations")
    parser.addoption("--metering-profile", default=None, help="Non-secret tenant/account profile JSON")
    parser.addoption("--metering-evidence-dir", default=None, help="Unique run directory for UI evidence")


def pytest_configure(config):
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y%m%d-%H%M%S")
    default = settings.REPORTS_DIR / "metering260901" / f"blackbox-{now}-{uuid4().hex[:8]}"
    worker = getattr(config, "workerinput", {})
    config._verified_run_dir = Path(worker.get("metering_evidence_dir") or config.getoption("--metering-evidence-dir") or default)


@pytest.hookimpl(optionalhook=True)
def pytest_configure_node(node):
    node.workerinput["metering_evidence_dir"] = str(node.config._verified_run_dir)


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "/verified/" not in item.nodeid.replace("\\", "/"):
            continue
        scenario = item.callspec.params["scenario"]
        if scenario["key"] in {"scan", "multi_api", "personal_owners", "personal_merge", "sensitive"}:
            item.add_marker(pytest.mark.timeout(900))
            item.add_marker(pytest.mark.slow)
        if scenario.get("hold_reason"):
            item.add_marker(pytest.mark.skip(reason=scenario["hold_reason"]))
        if scenario.get("requires_export") and not config.getoption("--metering-allow-export"):
            item.add_marker(pytest.mark.skip(reason="ENV_LIMITED: CSV export requires --metering-allow-export"))


@pytest.fixture(scope="session")
def verified_profile(request):
    profile = load_manifest()["default_profile"].copy()
    path = request.config.getoption("--metering-profile")
    if path:
        profile.update(json.loads(Path(path).read_text(encoding="utf-8")))
    assert_pre(settings.ENV, settings.PORTAL_BASE_URL, settings.CONSOLE_BASE_URL)
    if settings.USERNAME != profile["username"]:
        pytest.skip("ROLE_REQUIRED: 当前账号与已声明租户角色画像不同，请配置 --metering-profile")
    if not settings.PRE_PASSWORD:
        pytest.skip("ROLE_REQUIRED: 缺少PRE_PASSWORD，不回退使用UAT或生产密码")
    return profile


def guard_context(context, blocked):
    def route_guard(route):
        request = route.request
        if allowed_request(request.url, request.resource_type, request.method):
            route.continue_()
        elif optional_telemetry(request.url):
            # Suppress the observed shared tracker; it is not a PRE business failure.
            route.abort("blockedbyclient")
        else:
            from urllib.parse import urlparse

            parsed = urlparse(request.url)
            blocked.append(f"{parsed.scheme}://{parsed.netloc}{parsed.path}")
            route.abort("blockedbyclient")
    context.route("**/*", route_guard)


@pytest.fixture(scope="session")
def verified_browser(playwright, verified_profile):
    browser = playwright.chromium.launch(channel=settings.BROWSER_CHANNEL or None, headless=settings.HEADLESS)
    try:
        yield browser
    finally:
        browser.close()


@pytest.fixture(scope="session")
def verified_auth(verified_browser, verified_profile, request):
    states = {}
    failures = {}

    def authenticate(root, domain):
        role = "ordinary" if domain == "ordinary" else "cs" if domain == "cs" else "admin"
        key = (root, role)
        if key in failures:
            raise RuntimeError("该PRE域/租户登录已失败，本轮不重复尝试账号登录") from failures[key]
        if key in states:
            return states[key]
        logger.info("[metering] authenticate PRE origin=%s role=%s", root, role)
        context = verified_browser.new_context(viewport=verified_profile["viewport"], timezone_id="Asia/Shanghai")
        blocked = []
        guard_context(context, blocked)
        try:
            page = context.new_page()
            page.set_default_timeout(25000)
            page.set_default_navigation_timeout(45000)
            page.goto(root, wait_until="domcontentloaded")
            logger.info("[metering] authentication page loaded")
            user = page.get_by_text(verified_profile["display_name"], exact=True)
            gate = page.locator("#qrcont").or_(page.get_by_text("登录", exact=True)).or_(user)
            visible(gate)
            if not user.filter(visible=True).count():
                if not page.locator("#qrcont").filter(visible=True).count():
                    visible(page.get_by_text("登录", exact=True)).click()
                page.locator("#qrcont").wait_for(state="visible")
                frame = page.frame_locator("#qrcont")
                frame.locator("#usernameIn").fill(settings.USERNAME)
                frame.locator("#pwdIn").fill(settings.PRE_PASSWORD)
                frame.locator("#pwdLoginButton").click()
            logger.info("[metering] waiting for authenticated portal")
            page.wait_for_url(root + "**", timeout=45000)
            expect(visible(page.get_by_text(verified_profile["display_name"], exact=True))).to_be_visible()
            assert not blocked, f"ENV_MISMATCH: 被拦截的跨环境请求: {blocked}"
            states[key] = context.storage_state()
            logger.info("[metering] authentication completed")
            return states[key]
        except Exception as exc:
            failures[key] = exc
            directory = request.config._verified_run_dir / "auth"
            directory.mkdir(parents=True, exist_ok=True)
            from urllib.parse import urlparse

            host = urlparse(root).hostname
            try:
                page.screenshot(path=str(directory / f"{host}-{role}.png"), full_page=True)
                (directory / f"{host}-{role}.txt").write_text(page.locator("body").inner_text().replace(settings.PRE_PASSWORD, "[REDACTED]"), encoding="utf-8")
            except Exception:
                pass
            raise
        finally:
            context.close()

    def remember(root, domain, state):
        role = "ordinary" if domain == "ordinary" else "cs" if domain == "cs" else "admin"
        states[(root, role)] = state
    return authenticate, remember


class BlackboxPages:
    def __init__(self, browser, authenticate, profile):
        self.browser, self.profile = browser, profile
        self.authenticate, self.remember = authenticate
        self.domains = {}
        self.contexts = []
        self.blocked = []
        self.observations = {}

    def get(self, domain):
        if domain in self.domains:
            return self.domains[domain]
        root = settings.CONSOLE_BASE_URL if domain == "cs" else settings.PORTAL_BASE_URL
        root = root.rstrip("/") + "/"
        assert_pre(settings.ENV, root)
        state = self.authenticate(root, domain)
        context = self.browser.new_context(viewport=self.profile["viewport"], storage_state=state, accept_downloads=True, timezone_id="Asia/Shanghai")
        self.contexts.append(context)
        guard_context(context, self.blocked)
        page = context.new_page()
        page.set_default_timeout(20000)
        page.set_default_navigation_timeout(45000)
        model = MeteringBlackboxPage(page, domain, self.profile)
        self.domains[domain] = model
        model.open(root, remember_portal=lambda state: self.remember(root, domain, state))
        return model

    def close(self):
        for context in self.contexts:
            context.close()


@pytest.fixture
def blackbox_pages(verified_browser, verified_auth, verified_profile, request):
    provider = BlackboxPages(verified_browser, verified_auth, verified_profile)
    request.node._metering_provider = provider
    worker = getattr(request.config, "workerinput", {}).get("workerid", "controller")
    provider.output_dir = request.config._verified_run_dir / worker / request.node.callspec.params["scenario"]["key"]
    request.addfinalizer(provider.close)
    try:
        for domain in request.node.callspec.params["scenario"]["domains"]:
            provider.get(domain)
    except MissingMeteringData as exc:
        pytest.skip(str(exc) if str(exc).startswith("ROLE_REQUIRED:") else f"DATA_REQUIRED: {exc}")
    yield provider
    assert not provider.blocked, f"ENV_MISMATCH: 被拦截的跨环境请求: {provider.blocked}"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    result = yield
    report = result.get_result()
    provider = item.funcargs.get("blackbox_pages") or getattr(item, "_metering_provider", None)
    if provider is None or (report.when != "call" and not report.failed and not report.skipped):
        return
    scenario = item.callspec.params["scenario"]
    root = item.config._verified_run_dir
    worker = getattr(item.config, "workerinput", {}).get("workerid", "controller")
    directory = root / worker / scenario["key"]
    directory.mkdir(parents=True, exist_ok=True)
    files = []
    current_data = {}
    for domain, model in provider.domains.items():
        responses = []
        for response in model.responses[-20:]:
            try:
                from urllib.parse import urlparse
                responses.append({"path": urlparse(response.url).path, "request": response.request.post_data,
                                  "status": response.status, "body": response.json()})
            except Exception:
                pass
        current_data[domain] = {"current_page": model.last_data, "scanned": model.scanned,
                                "responses": responses, "navigation": model.navigation}
        path = directory / f"{domain}.png"
        try:
            model.page.screenshot(path=str(path), full_page=True)
            files.append(str(path))
        except Exception:
            # Evidence capture must not overwrite the actual test outcome.
            pass
    path = directory / "observations.json"
    path.write_text(json.dumps({"source_run": load_manifest()["source_run"], "scenario": scenario["key"],
                                "case_ids": scenario["case_ids"], "current_outcome": report.outcome,
                                "viewport": provider.profile["viewport"], "blocked_requests": provider.blocked,
                                "observations": provider.observations, "current_data": current_data, "screenshots": files},
                               ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    report.user_properties.append(("metering_artifacts", str(path)))
