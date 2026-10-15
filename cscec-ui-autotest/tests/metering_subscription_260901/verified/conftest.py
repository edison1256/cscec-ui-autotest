"""Isolated PRE/PROD sessions, production read guards, and per-run evidence."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from playwright.sync_api import expect

from config.settings import settings
from core.metering_blackbox_contract import MissingMeteringData, allowed_request, assert_metering_environment, load_manifest, optional_telemetry
from core.metering_trace import MeteringTraces
from pages.metering_blackbox_page import MeteringBlackboxPage, visible

logger = logging.getLogger(__name__)


def pytest_addoption(parser):
    parser.addoption("--metering-readonly-preflight", action="store_true", default=False,
                     help="Exercise production readonly request policy against PRE only")
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
        if scenario.get("requires_export"):
            if settings.ENV == "prod":
                item.add_marker(pytest.mark.skip(reason="WRITE_BLOCKED: export creates tasks and is excluded from PROD readonly regression"))
            elif not config.getoption("--metering-allow-export"):
                item.add_marker(pytest.mark.skip(reason="ENV_LIMITED: CSV export requires --metering-allow-export"))


@pytest.fixture(scope="session")
def verified_profile(request):
    profile = load_manifest()["default_profile"].copy()
    if settings.ENV == "prod":
        # PRE menu identifiers and a PRE resource name are not production fixtures.
        profile.update(personal_subscription_path=None, resource_catalog_path=None, query_resource=None)
    path = request.config.getoption("--metering-profile")
    if path:
        supplied = json.loads(Path(path).read_text(encoding="utf-8"))
        if settings.ENV == "prod" and supplied.get("environment") != "prod":
            raise ValueError("ENV_MISMATCH: production profile must explicitly declare environment=prod")
        profile.update(supplied)
    if profile.get("environment", settings.ENV) != settings.ENV:
        raise ValueError("ENV_MISMATCH: profile belongs to another environment")
    profile["environment"] = settings.ENV
    profile["readonly_requests"] = settings.ENV == "prod" or request.config.getoption("--metering-readonly-preflight")
    assert_metering_environment(settings.ENV, settings.PORTAL_BASE_URL, settings.CONSOLE_BASE_URL)
    if settings.USERNAME != profile["username"]:
        pytest.skip("ROLE_REQUIRED: 当前账号与已声明租户角色画像不同，请配置 --metering-profile")
    if not getattr(settings, settings.ENV.upper() + "_PASSWORD"):
        pytest.skip(f"ROLE_REQUIRED: 缺少{settings.ENV.upper()}_PASSWORD，不回退使用其他环境密码")
    return profile


def guard_context(context, blocked, readonly=False):
    def route_guard(route):
        request = route.request
        if allowed_request(request.url, request.resource_type, request.method, env=settings.ENV, readonly=readonly):
            route.continue_()
        elif optional_telemetry(request.url, env=settings.ENV):
            # Navigation tracking is blocked too, but is not a business-test failure.
            logger.debug("[metering] optional navigation tracking suppressed")
            route.abort("blockedbyclient")
        else:
            from urllib.parse import urlparse

            parsed = urlparse(request.url)
            blocked.append(f"{request.method} {parsed.scheme}://{parsed.netloc}{parsed.path}")
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
    password = getattr(settings, settings.ENV.upper() + "_PASSWORD")

    def authenticate(root, domain):
        role = "ordinary" if domain == "ordinary" else "cs" if domain == "cs" else "admin"
        key = (root, role)
        if key in failures:
            raise RuntimeError("该环境/租户登录已失败，本轮不重复尝试账号登录") from failures[key]
        if key in states:
            return states[key]
        logger.info("[metering] authenticate env=%s origin=%s role=%s", settings.ENV, root, role)
        context = verified_browser.new_context(viewport=verified_profile["viewport"], timezone_id="Asia/Shanghai")
        blocked = []
        script_urls = set()
        context.on("response", lambda response: script_urls.add(response.url)
                   if response.request.resource_type == "script" else None)
        guard_context(context, blocked, readonly=verified_profile["readonly_requests"])
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
                frame.locator("#pwdIn").fill(password)
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
            assets = sorted({urlparse(url)._replace(query="", fragment="").geturl() for url in script_urls})
            (directory / f"{host}-{role}-assets.json").write_text(json.dumps(assets, indent=2), encoding="utf-8")
            try:
                page.screenshot(path=str(directory / f"{host}-{role}.png"), full_page=True)
                (directory / f"{host}-{role}.txt").write_text(page.locator("body").inner_text().replace(password, "[REDACTED]"), encoding="utf-8")
            except Exception:
                pass
            if blocked:
                raise AssertionError(f"WRITE_BLOCKED/ENV_MISMATCH: 登录阶段请求被拦截: {blocked}") from exc
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
        assert_metering_environment(settings.ENV, root)
        state = self.authenticate(root, domain)
        context = self.browser.new_context(viewport=self.profile["viewport"], storage_state=state, accept_downloads=True, timezone_id="Asia/Shanghai")
        self.contexts.append(context)
        self.traces.start(context, self.output_dir / f"{domain}-trace.zip")
        guard_context(context, self.blocked, readonly=self.profile["readonly_requests"])
        page = context.new_page()
        page.set_default_timeout(20000)
        page.set_default_navigation_timeout(45000)
        model = MeteringBlackboxPage(page, domain, self.profile)
        self.domains[domain] = model
        try:
            model.open(root, remember_portal=lambda state: self.remember(root, domain, state))
        except Exception as exc:
            if self.blocked:
                raise AssertionError(f"WRITE_BLOCKED/ENV_MISMATCH: 页面初始化请求被拦截: {self.blocked}") from exc
            raise
        return model

    def close(self):
        for context in self.contexts:
            try:
                self.traces.stop(context)
            finally:
                context.close()


@pytest.fixture
def blackbox_pages(verified_browser, verified_auth, verified_profile, request):
    provider = BlackboxPages(verified_browser, verified_auth, verified_profile)
    request.node._metering_provider = provider
    worker = getattr(request.config, "workerinput", {}).get("workerid", "controller")
    provider.output_dir = request.config._verified_run_dir / worker / request.node.callspec.params["scenario"]["key"]
    provider.traces = MeteringTraces(request.config.getoption("tracing", default="off"))
    request.addfinalizer(provider.close)
    try:
        for domain in request.node.callspec.params["scenario"]["domains"]:
            provider.get(domain)
    except MissingMeteringData as exc:
        pytest.skip(str(exc) if str(exc).startswith("ROLE_REQUIRED:") else f"DATA_REQUIRED: {exc}")
    yield provider
    assert not provider.blocked, f"WRITE_BLOCKED/ENV_MISMATCH: 被拦截的非只读或跨环境请求: {provider.blocked}"


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    result = yield
    report = result.get_result()
    provider = item.funcargs.get("blackbox_pages") or getattr(item, "_metering_provider", None)
    if provider is not None:
        provider.traces.failed |= report.failed
        if report.when == "teardown":
            paths = provider.traces.finalize()
            report.user_properties.append(("metering_traces", json.dumps(paths)))
            report.user_properties.append(("metering_trace_errors", json.dumps(provider.traces.errors)))
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
