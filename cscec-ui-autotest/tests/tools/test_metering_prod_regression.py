from __future__ import annotations

import json
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import run_tests
from core.metering_blackbox_contract import allowed_request, assert_metering_environment, load_manifest, optional_telemetry
from core.metering_trace import MeteringTraces
from pages.metering_blackbox_page import metering_route


@pytest.mark.parametrize("env,host", [("pre", "cloud-pre.cscec.com"), ("prod", "cloud.cscec.com"), ("prod", "irp.cscec.com")])
def test_matching_environment_is_accepted(env, host):
    assert_metering_environment(env, f"https://{host}/")


@pytest.mark.parametrize("env,url", [
    ("prod", "https://cloud-pre.cscec.com/"), ("pre", "https://irp.cscec.com/"),
    ("uat", "https://cloud-uat.cscec.com/"), ("prod", "http://cloud.cscec.com/"),
    ("prod", "https://cloud.cscec.com:8443/"), ("prod", "https://user@cloud.cscec.com/"),
])
def test_cross_environment_and_nonstandard_origins_fail(env, url):
    with pytest.raises(ValueError, match="ENV_MISMATCH"):
        assert_metering_environment(env, url)


@pytest.mark.parametrize("path,method,expected", [
    ("workbench/quota-instance/aggregate", "POST", True),
    ("quota-instance/aggregateForConsole", "POST", True),
    ("quota-instance/listByIds", "POST", True),
    ("quota-instance-order/findByOrderIds", "POST", True),
    ("quota-daily/listSummary", "POST", True),
    ("quota-daily/detail", "GET", True),
    ("compt/apply/history/list", "POST", True),
    ("component-portal/list", "POST", True),
    ("quota-instance/save", "POST", False),
    ("quota-instance/delete", "GET", False),
    ("quota-instance/list", "DELETE", False),
    ("quota-instance/aggregate/update/list", "POST", False),
    ("quota-instance/%2e%2e/delete", "GET", False),
    ("quota-daily/export", "GET", False),
    ("export/createTask", "POST", False),
    ("export/download", "GET", False),
    ("unknown/mutate", "POST", False),
    ("resources/save", "POST", False),
    ("resources/update", "GET", False),
])
def test_production_business_requests_are_readonly(path, method, expected):
    assert allowed_request(f"https://irp.cscec.com/irp-api/{path}", "fetch", method, env="prod") is expected


def test_prod_policy_covers_other_resource_types_and_auth_separately():
    assert not allowed_request("https://irp.cscec.com/irp-api/quota-instance/save", "other", "POST", env="prod")
    assert not allowed_request("https://cloud-pre.cscec.com/irp-api/quota-instance/list", "fetch", "POST", env="prod")
    assert not allowed_request("https://iamuat.cscec.com/irp-api/quota-instance/list", "fetch", "POST", env="prod")
    assert allowed_request("https://iam.cscec.com/cas/login", "document", "POST", env="prod")
    assert allowed_request("https://irp-pre.cscec.com/irp-api/quota-instance/list", "fetch", "POST", readonly=True)
    assert not allowed_request("https://irp-pre.cscec.com/irp-api/quota-instance/save", "fetch", "POST", readonly=True)
    assert allowed_request("https://cloud.cscec.com/irp-api/irp-portal-public/banner/listForPortalNoAuth", "fetch", "POST", env="prod")
    assert allowed_request("https://cloud.cscec.com/portal/loginConfig/getLoginConfigForLogin", "fetch", "POST", env="prod")


def test_prod_release_flag_never_enables_legacy_or_uat(monkeypatch):
    from tests.metering_subscription_260901 import conftest as plugin

    config = SimpleNamespace(getoption=lambda option: True)
    modern = "tests/metering_subscription_260901/verified/test_verified_workflows.py::test_verified_workflow[scan]"
    legacy = "tests/metering_subscription_260901/test_m3.py::test_example"
    monkeypatch.setattr(plugin.settings, "ENV", "prod")
    assert plugin.environment_enabled(config, modern)
    assert not plugin.environment_enabled(config, legacy)
    assert not plugin.environment_enabled(SimpleNamespace(getoption=lambda option: False), modern)
    monkeypatch.setattr(plugin.settings, "ENV", "uat")
    assert not plugin.environment_enabled(config, modern)


@pytest.mark.parametrize("path", ["/udp-monitor/logging", "/integration-portal/recentUseMenu/useMenu"])
def test_navigation_tracking_is_suppressed_without_allowing_writes(path):
    url = "https://cloud.cscec.com" + path
    assert not allowed_request(url, "fetch", "POST", env="prod")
    assert optional_telemetry(url, env="prod")
    assert not optional_telemetry(url, env="pre")
    assert not optional_telemetry("https://cloud.cscec.com/irp-api/quota-instance/save", env="prod")


@pytest.mark.parametrize("path", [
    "/irp-api/irp-portal-workbench/developer-community-post-portal/postPortalWorkbench",
    "/irp-api/irp-portal-console/developer-community-post-portal/postPortalConsole",
    "/irp-api/irp-portal-console/link/checkNoAuth",
    "/irp-api/irp-portal-console/knowledge-center/queryNoAuth",
    "/irp-api/irp-portal-public/tenant/viewBatch",
    "/basedata/api/tenant/getUserJobByUserCodeAndDataSource",
    "/engine/metadata/getMenuPageName",
    "/auth/resolve/getNoGrantButtons",
])
def test_verified_initialization_queries_do_not_enable_sibling_mutations(path):
    url = "https://irp.cscec.com" + path
    assert allowed_request(url, "fetch", "POST", env="prod")
    assert not allowed_request(url + "/save", "fetch", "POST", env="prod")
    assert not allowed_request(url, "fetch", "DELETE", env="prod")
    assert not allowed_request(url.replace("irp.cscec.com", "irp-pre.cscec.com"), "fetch", "POST", env="prod")


@pytest.mark.parametrize("password", ["", "prod-test-only"])
def test_prod_profile_never_inherits_pre_password_or_menu_identifiers(monkeypatch, password):
    from tests.metering_subscription_260901.verified import conftest as plugin

    for name, value in {"ENV": "prod", "PORTAL_BASE_URL": "https://cloud.cscec.com/",
                        "CONSOLE_BASE_URL": "https://irp.cscec.com/", "USERNAME": "20431644",
                        "PROD_PASSWORD": password, "PRE_PASSWORD": "pre-test-only"}.items():
        monkeypatch.setattr(plugin.settings, name, value)
    request = SimpleNamespace(config=SimpleNamespace(getoption=lambda option: None))
    if not password:
        with pytest.raises(pytest.skip.Exception, match="PROD_PASSWORD"):
            plugin.verified_profile.__wrapped__(request)
    else:
        profile = plugin.verified_profile.__wrapped__(request)
        assert profile["environment"] == "prod" and profile["readonly_requests"]
        assert profile["query_resource"] is profile["personal_subscription_path"] is profile["resource_catalog_path"] is None


def test_export_has_write_marker_and_is_not_in_production_readonly_selection():
    from tests.metering_subscription_260901.verified.test_verified_workflows import test_verified_workflow

    parametrization = next(mark for mark in test_verified_workflow.pytestmark if mark.name == "parametrize")
    cases = parametrization.args[1]
    readonly = [case for case in cases if any(mark.name == "readonly" for mark in case.marks)]
    writes = [case for case in cases if any(mark.name == "write" for mark in case.marks)]
    assert len(readonly) + len(writes) == len(load_manifest()["scenarios"])
    assert {case.values[0]["key"] for case in writes} == {"repeat_export"}
    assert len(readonly) == 38
    assert len({cid for case in readonly for cid in case.values[0]["case_ids"]}) == 61


def test_production_export_is_rejected_before_any_browser_action():
    from tests.metering_subscription_260901.verified.test_verified_workflows import export_workflow

    with pytest.raises(AssertionError, match="WRITE_BLOCKED"):
        export_workflow(SimpleNamespace(profile={"environment": "prod"}))


@pytest.mark.parametrize("suite,mark", [("metering", "metering_blackbox_verified"), (None, "smoke and readonly")])
def test_runner_selects_only_audited_metering_path_and_preserves_default_prod(tmp_path, monkeypatch, suite, mark):
    commands = []
    monkeypatch.setenv("ENV", "pre")
    monkeypatch.setattr(run_tests, "PROJECT_DIR", tmp_path)
    monkeypatch.setattr(run_tests, "_load_env_file", lambda: None)
    monkeypatch.setattr(run_tests, "_project_python", lambda: "python")
    monkeypatch.setattr(run_tests, "_prepare_allure_results", lambda **kwargs: None)
    monkeypatch.setattr(run_tests, "_run", lambda cmd: commands.append(cmd) or 0)
    args = ["run_tests.py", "--env", "prod", "--dry-run"]
    if suite:
        args += ["--prod-suite", suite]
    monkeypatch.setattr(sys, "argv", args)
    with pytest.raises(SystemExit) as exc:
        run_tests.main()
    assert exc.value.code == 0
    cmd = commands[0]
    assert mark in cmd[cmd.index("-m", 3) + 1]
    assert "--collect-only" in cmd
    if suite:
        assert Path(cmd[3]).as_posix() == "tests/metering_subscription_260901/verified"
        assert "--metering-prod-ready" in cmd
        assert cmd[cmd.index("--tracing") + 1] == "retain-on-failure"
    else:
        assert "--metering-prod-ready" not in cmd


@pytest.fixture(scope="module")
def local_browser(playwright):
    browser = playwright.chromium.launch(headless=True)
    yield browser
    browser.close()


@pytest.mark.parametrize("key,new_label,old_label", [
    ("wb_columns", "资源发布方", "资源所属方"),
    ("wb_order_columns", "订阅人所在租户", "订阅人所在组织"),
])
@pytest.mark.parametrize("legacy", [False, True])
def test_confirmed_column_contract_is_enforced_in_workflow(monkeypatch, key, new_label, old_label, legacy):
    from tests.metering_subscription_260901.verified import test_verified_workflows as workflow

    expected = workflow.WB_HEADERS if key == "wb_columns" else workflow.ORDER_HEADERS
    actual = tuple(old_label if legacy and column == new_label else column for column in expected)
    raw = {"resourceName": "current-resource", "serviceModeName": "current-mode"}
    model = SimpleNamespace(
        page=object(), headers=actual, last_data={"list": [raw]}, order_headers=actual,
        sample_account=lambda **kwargs: (object(), raw),
        orders=lambda *args: (object(), ["current-order"]),
        order_form=lambda order: {"资源名称": raw["resourceName"], "服务模式": raw["serviceModeName"], "订单状态": "订阅成功"},
    )
    provider = SimpleNamespace(get=lambda domain: model, observations={})
    monkeypatch.setattr(workflow, "ui_table", lambda *args: (object(), actual))
    if legacy:
        with pytest.raises(AssertionError, match="CONTRACT_DIFFERENCE"):
            workflow.run_workflow(provider, key)
    else:
        workflow.run_workflow(provider, key)


@pytest.mark.parametrize("mode,failed,retained", [
    ("off", True, False), ("on", False, True),
    ("retain-on-failure", False, False), ("retain-on-failure", True, True),
])
def test_real_trace_zip_retention_and_click_events(local_browser, tmp_path, mode, failed, retained):
    traces = MeteringTraces(mode)
    context = local_browser.new_context()
    path = tmp_path / "scenario" / "wb-trace.zip"
    traces.start(context, path)
    page = context.new_page()
    page.set_content('<button onclick="this.innerText=\'expanded\'">expand</button>')
    page.get_by_role("button", name="expand").click()
    traces.stop(context)
    context.close()
    traces.failed = failed
    paths = traces.finalize()
    assert not traces.errors
    assert path.exists() is retained
    assert bool(paths) is retained
    if retained:
        with zipfile.ZipFile(path) as archive:
            names = [name for name in archive.namelist() if name.endswith(".trace")]
            events = [json.loads(line) for name in names for line in archive.read(name).decode().splitlines()]
            assert any(event.get("type") == "frame-snapshot" for event in events)
            assert any(event.get("method") == "click" for event in events)


def test_production_route_uses_current_dom_and_rejects_pre_links(local_browser):
    context = local_browser.new_context()
    page = context.new_page()
    fragment = "/subscription/apiResource"
    profile = {"environment": "prod"}
    target = "https://cloud.cscec.com/udpweb/#/sub/resource/subscription/apiResource?menuCode=production-id"
    page.set_content(f'<a href="{target}">API</a>')
    assert metering_route(page, "https://cloud.cscec.com/", profile, "personal_subscription_path", fragment) == target
    page.set_content('<a href="https://cloud-pre.cscec.com/#/subscription/apiResource">API</a>')
    with pytest.raises(ValueError, match="ENV_MISMATCH"):
        metering_route(page, "https://cloud.cscec.com/", profile, "personal_subscription_path", fragment)
    context.close()


def test_trace_cleanup_failure_does_not_mask_test_result(tmp_path, monkeypatch):
    path = tmp_path / "trace.zip"
    path.touch()
    traces = MeteringTraces("retain-on-failure")
    traces.files = [path]
    def locked_file(*args, **kwargs):
        raise PermissionError("file in use")
    monkeypatch.setattr(Path, "unlink", locked_file)
    assert traces.finalize() == [str(path)]
    assert traces.errors == ["Trace cleanup failed: PermissionError"]
