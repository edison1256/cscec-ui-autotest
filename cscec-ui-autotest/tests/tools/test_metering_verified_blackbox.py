from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from core.metering_blackbox_contract import (
    ACCOUNT_HEADERS, WB_HEADERS, USAGE_HEADERS, DAILY_HEADERS, MissingMeteringData, allowed_request, amount,
    align_records, assert_children, assert_daily, assert_daily_response, assert_export, assert_pre, load_manifest, optional_telemetry,
)
from pages.metering_blackbox_page import MeteringBlackboxPage, response_data, ui_rows, watch_downloads
from tools.metering_results_260901 import ResultRecorder


def sample(count=7):
    raw = {"subscriptionCount": count, "resourceId": "resource", "serviceMode": "mode",
           "instanceIds": [f"account-{i}" for i in range(count)]}
    parent = {"订阅数量": str(count), "资源名称": "resource-label", "服务模式": "mode-label"}
    accounts = [{"id": f"account-{i}", "resourceId": "resource", "serviceMode": "mode", "applyAppName": f"app-{i}", "usedQuota": i} for i in range(count)]
    children = [{"资源名称": "resource-label", "服务模式": "mode-label", "订阅应用": f"app-{i}", "已调用额": str(i)} for i in range(count)]
    return parent, children, raw, accounts


@pytest.mark.parametrize("count", [1, 2, 7, 16])
def test_parent_counts_are_derived_from_current_data(count):
    assert_children(*sample(count))


@pytest.mark.parametrize("mutation", ["count", "resource", "mode", "app", "ids", "used"])
def test_wrong_parent_account_binding_never_passes(mutation):
    parent, children, raw, accounts = sample()
    if mutation == "count":
        parent["订阅数量"] = "1"
    elif mutation == "resource":
        children[0]["资源名称"] = "other"
    elif mutation == "mode":
        accounts[0]["serviceMode"] = "other"
    elif mutation == "app":
        children[0]["订阅应用"] = "other"
    elif mutation == "used":
        children[0]["已调用额"] = "100.3"
    else:
        accounts[0]["id"] = "old-run-id"
    with pytest.raises(AssertionError):
        assert_children(parent, children, raw, accounts)


def test_merged_account_count_is_not_original_instance_or_order_count():
    parent, children, raw, accounts = sample(2)
    raw["instanceIds"] = ["purchase-a", "purchase-b", "purchase-c"]
    accounts[0]["instanceIds"] = ["purchase-a", "purchase-b"]
    accounts[1]["instanceIds"] = ["purchase-c"]
    assert_children(parent, children, raw, accounts)


def test_response_order_is_not_ui_account_identity():
    records = [{"resourceName": "r", "serviceModeName": "m", "applyAppName": app, "orderIds": [app]} for app in ("a", "b")]
    fields = {"资源名称": "resourceName", "服务模式": "serviceModeName", "订阅应用": "applyAppName"}
    rows = [{"资源名称": "r", "服务模式": "m", "订阅应用": app} for app in ("b", "a")]
    assert align_records(rows, records, fields)[0]["orderIds"] == ["b"]
    with pytest.raises(AssertionError, match="重复业务组合"):
        align_records(rows, [records[0], records[0]], fields)
    rows[0]["订阅应用"] = "foreign"
    with pytest.raises(AssertionError, match="业务组合"):
        align_records(rows, records, fields)


@pytest.mark.parametrize("env,url", [
    ("uat", "https://cloud-pre.cscec.com/"), ("prod", "https://cloud-pre.cscec.com/"),
    ("pre", "https://cloud.cscec.com/"), ("pre", "http://cloud-pre.cscec.com/"),
])
def test_env_and_origin_guard(env, url):
    with pytest.raises(ValueError, match="ENV_MISMATCH"):
        assert_pre(env, url)


def test_pre_only_network_policy_and_shared_tracker_suppression():
    assert allowed_request("https://irp-pre.cscec.com/irp-api/query", "fetch")
    assert not allowed_request("https://irp.cscec.com/irp-api/query", "fetch")
    assert not allowed_request("https://iam.cscec.com/irp-api/query", "fetch")
    assert not allowed_request("https://cloud-uat.cscec.com/", "document")
    assert allowed_request("https://iam.cscec.com/cas/login", "document")
    assert allowed_request("https://iamuat.cscec.com/cas/login", "document")
    assert not allowed_request("https://iamuat.cscec.com/irp-api/query", "fetch")
    tracker = "https://data-track-api.cscec.com/apipool"
    assert optional_telemetry(tracker) and not allowed_request(tracker, "xhr")
    font = "https://at.alicdn.com/t/c/font_123_abc.js"
    assert allowed_request(font, "fetch", "GET")
    assert not allowed_request(font, "fetch", "POST")


def test_daily_values_use_decimal_consistency_not_a_fixed_total():
    rows = [{"日期": "2026-10-02", "已调用额": "0.2"}, {"日期": "2026-10-01", "已调用额": "0.1"}]
    assert_daily(rows, len(rows), "0.3")
    with pytest.raises(AssertionError, match="合计"):
        assert_daily(rows, len(rows), "0.4")
    with pytest.raises(AssertionError, match="全部分页"):
        assert_daily(rows[:1], len(rows), "0.2")
    with pytest.raises(MissingMeteringData):
        assert_daily([], 0, "0")


def test_daily_rows_cannot_hide_a_zero_day_or_wrong_call_count():
    rows = [{"日期": "2026-10-01", "已调用次数": "3", "已调用额": "0.3"}]
    data = {"total": 1, "list": [{"usageDate": "2026-10-01", "callCount": "3", "callQuota": "0.3"}]}
    assert_daily_response(rows, data)
    data["list"][0]["callCount"] = "2"
    with pytest.raises(AssertionError, match="次数"):
        assert_daily_response(rows, data)
    data["list"].append({"usageDate": "2026-09-30", "callCount": "0", "callQuota": "0"})
    data["total"] = 2
    with pytest.raises(AssertionError, match="总数"):
        assert_daily_response(rows, data)


@pytest.mark.parametrize("value", ["不限次数", "1 Credits", "-", "", "-1"])
def test_unit_or_unlimited_text_cannot_be_a_numeric_usage(value):
    with pytest.raises(AssertionError):
        amount(value)


def test_equivalent_api_numeric_formats_are_not_different_amounts():
    assert amount("4.4e-5") == amount("0.0000440")
    assert amount("1,000.0000") == amount("1e3")


def test_export_checks_actual_file_against_all_ui_pages():
    expected = [{"日期": "2026-10-02", "已调用次数": "2", "已调用额": "0.2"},
                {"日期": "2026-10-01", "已调用次数": "1", "已调用额": "0.1"}]
    blob = "日期,已调用次数,已调用额\n2026-10-01,1,0.1\n2026-10-02,2,0.2\n".encode("utf-8-sig")
    assert assert_export(blob, expected)["rows"] == len(expected)
    with pytest.raises(AssertionError, match="全部分页"):
        assert_export(blob, expected[:1])
    assert assert_export(b"\xef\xbb\xbf" + blob, expected)["double_bom"]
    assert assert_export(blob.replace("已调用额".encode(), "已调用额度".encode()), expected)["rows"] == len(expected)


def test_manifest_accounts_for_every_historical_pass_without_promotion():
    data = load_manifest()
    assert len(data["cases"]) == 62
    held = [s for s in data["scenarios"] if s.get("hold_reason")]
    assert {cid for s in held for cid in s["case_ids"]} == {"M4.3.4", "M6.2.3", "M7.1.2"}
    assert len(data["source_record_sha256"]) == 64
    assert not any("status" in s for s in data["scenarios"])


def test_group_reports_record_every_outline_id_and_archive_current_run(tmp_path):
    node = "tests/metering_subscription_260901/verified/test_verified_workflows.py::test_verified_workflow[scan]"
    ids = ["M2.4.2", "M3.1.1", "M3.1.3"]
    report = SimpleNamespace(nodeid=node, when="setup", outcome="skipped", failed=False, skipped=True,
                             longrepr="ENV_MISMATCH: PRE only", user_properties=[("metering_case_ids", json.dumps(ids))])
    recorder = ResultRecorder(tmp_path / "results.json", "uat")
    recorder.consume(report)
    recorder.flush(0)
    assert set(recorder.results) == set(ids)
    assert all(row["status"] == "skipped" for row in recorder.results.values())
    archive = tmp_path / "runs" / recorder.run_id / "results.json"
    assert json.loads(archive.read_text(encoding="utf-8")) == json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))


def test_business_error_is_not_treated_as_missing_sample():
    response = SimpleNamespace(status=200, json=lambda: {"code": 50000, "data": []})
    with pytest.raises(AssertionError, match="业务返回失败"):
        response_data(response)


@pytest.fixture(scope="module")
def dom_browser(playwright):
    browser = playwright.chromium.launch(headless=True)
    try:
        yield browser
    finally:
        browser.close()


@pytest.fixture
def dom_page(dom_browser):
    context = dom_browser.new_context()
    try:
        yield context.new_page()
    finally:
        context.close()


def test_cached_expansion_requires_current_parent_ids_and_real_rows(dom_page):
    parent, children, raw, accounts = sample(2)
    for child in children:
        child["操作"] = "查看订单明细"
    raw.update(resourceName=parent["资源名称"], resourceCode="code", serviceModeName=parent["服务模式"])
    th = lambda headers: "".join(f"<th>{name}</th>" for name in headers)
    child_tr = "".join("<tr>" + "".join(f"<td>{row.get(name, '0')}</td>" for name in ACCOUNT_HEADERS) + "</tr>" for row in children)
    dom_page.set_content(f"""<table><thead><tr>{th(WB_HEADERS)}</tr></thead><tbody>
      <tr><td>resource-label</td><td>code</td><td>mode-label</td><td>publisher</td><td>2</td>
      <td><button onclick="document.getElementById('panel').hidden=!document.getElementById('panel').hidden;this.innerText=this.innerText==='查看'?'收起':'查看'">查看</button></td></tr>
      <tr id="panel" hidden><td colspan="6"><table><thead><tr>{th(ACCOUNT_HEADERS)}</tr></thead><tbody>{child_tr}</tbody></table></td></tr>
      </tbody></table>""")
    model = MeteringBlackboxPage(dom_page, "wb", {})
    model.last_data = {"list": [raw], "total": 1}
    response = SimpleNamespace(url="https://cloud-pre.cscec.com/irp-api/workbench/quota-instance/listByIds", status=200,
                               request=SimpleNamespace(post_data=json.dumps({"instanceIds": raw["instanceIds"]})),
                               json=lambda: {"code": 0, "data": accounts})
    model.responses.append(response)
    row, panel, current = model.expand()
    assert len(ui_rows(panel, ACCOUNT_HEADERS)) == len(current) == 2
    model.collapse(row)
    model.expand()  # UI cache is allowed, but not evidence from another parent.
    model.collapse(row)
    model.responses.clear()
    wrong = copy.deepcopy(accounts)
    wrong[0]["id"] = "foreign-account"
    model.responses.append(SimpleNamespace(url=response.url, request=response.request, status=200, json=lambda: {"code": 0, "data": wrong}))
    with pytest.raises(AssertionError, match="当前父行"):
        model.expand()


def test_daily_click_ignores_measurement_row_and_requires_real_pagination(dom_page):
    th = lambda headers: "".join(f"<th>{name}</th>" for name in headers)
    dom_page.route("**/quota-daily/detail*", lambda route: route.fulfill(
        json={"code": 0, "data": {"total": 1, "list": [{"usageDate": "2026-10-01", "callCount": "3", "callQuota": "0.3"}]}},
        headers={"Access-Control-Allow-Origin": "*"}))
    dom_page.set_content(f"""<div id="usage"><table><thead><tr>{th(USAGE_HEADERS)}</tr></thead><tbody>
        <tr><td></td><td></td><td></td></tr>
        <tr><td>api</td><td>0.3</td><td><button onclick="fetch('https://cloud-pre.cscec.com/irp-api/quota-daily/detail?quotaInstanceId=fixture&amp;eipApiId=fixture').then(() => document.getElementById('days').hidden=false)">查看明细</button></td></tr>
        </tbody></table></div><div role="dialog" id="days" hidden>
        <table><thead><tr>{th(DAILY_HEADERS)}</tr></thead><tbody><tr><td>2026-10-01</td><td>3</td><td>0.3</td></tr></tbody></table>
        <div>第1-1条/总共1条</div></div>""")
    model = MeteringBlackboxPage(dom_page, "wb", {})
    model.usage_summaries = [{"eipApiName": "api", "quotaInstanceId": "fixture", "eipApiId": "fixture"}]
    _, rows, total, used = model.daily(dom_page.locator("#usage"))
    assert_daily(rows, total, used)
    with pytest.raises(MissingMeteringData, match="没有第二页"):
        model.daily(dom_page.locator("#usage"), require_pagination=True)


def test_same_mode_label_is_bound_by_clicked_request_instance_ids(dom_page):
    th = lambda headers: "".join(f"<th>{name}</th>" for name in headers)
    records = [{"resourceCode": "code", "resourceId": "resource", "serviceModeName": "mode", "serviceMode": f"mode-{key}",
                "instanceIds": [f"instance-{key}"], "subscriptionCount": 1} for key in ("a", "b")]
    def fulfill(route):
        key = json.loads(route.request.post_data)["instanceIds"][0][-1]
        route.fulfill(json={"code": 0, "data": [{"id": f"instance-{key}", "instanceIds": [f"instance-{key}"],
                      "resourceId": "resource", "serviceMode": f"mode-{key}", "applyAppName": f"app-{key}", "usedQuota": 0}]},
                      headers={"Access-Control-Allow-Origin": "*"})
    dom_page.route("**/quota-instance/listByIds", fulfill)
    html = []
    for key in ("b", "a"):
        html.append(f"""<tr><td>resource</td><td>code</td><td>mode</td><td>publisher</td><td>1</td><td>
          <button onclick='fetch("https://cloud-pre.cscec.com/irp-api/quota-instance/listByIds", {{method:"POST",body:JSON.stringify({{"instanceIds":["instance-{key}"]}})}}).then(() => {{document.getElementById("{key}").hidden=false;this.innerText="收起"}})'>查看</button></td></tr>
          <tr id="{key}" hidden><td colspan="6"><table><thead><tr>{th(ACCOUNT_HEADERS)}</tr></thead><tbody><tr>
          <td>resource</td><td>mode</td><td>app-{key}</td><td>publisher</td><td>date</td><td>date</td><td>可用</td><td>0</td><td>0</td><td>0</td><td>查看订单明细</td>
          </tr></tbody></table></td></tr>""")
    dom_page.set_content(f"<table><thead><tr>{th(WB_HEADERS)}</tr></thead><tbody>{''.join(html)}</tbody></table>")
    model = MeteringBlackboxPage(dom_page, "wb", {})
    model.last_data = {"total": len(records), "list": records}
    _, _, accounts = model.expand(0)
    assert accounts[0]["serviceMode"] == model.last_expanded_raw["serviceMode"] == "mode-b"
    assert model.last_expanded_raw["instanceIds"] != records[0]["instanceIds"]


def test_download_watch_supports_existing_and_popup_pages(dom_page):
    downloads = watch_downloads(dom_page.context)
    for page in (dom_page, dom_page.context.new_page()):
        page.set_content('<a download="test.csv" href="data:text/csv,a%2Cb%0A1%2C2">download</a>')
        with page.expect_download():
            page.get_by_role("link", name="download").click()
    assert len(downloads) == 2


def test_readonly_checks_actions_not_business_resource_names(dom_page):
    from tests.metering_subscription_260901.verified.test_verified_workflows import assert_no_write

    dom_page.set_content('<div id="scope"><span>增购服务组件</span><button>查看</button></div>')
    assert_no_write(dom_page.locator("#scope"))
    dom_page.set_content('<div id="scope"><button aria-label="增购"></button></div>')
    with pytest.raises(AssertionError, match="修改入口"):
        assert_no_write(dom_page.locator("#scope"))


def test_partial_scope_is_preserved_in_result_and_outline(tmp_path):
    from tools.generate_metering_outline_260901 import annotate

    node = "tests/metering_subscription_260901/verified/test_verified_workflows.py::test_verified_workflow[wb_reset]"
    note = "统计方式分支未验证"
    report = SimpleNamespace(nodeid=node, when="call", outcome="passed", failed=False, skipped=False, longrepr=None,
                             user_properties=[("metering_case_ids", '["M2.2.4"]'),
                                              ("metering_scope_notes", json.dumps({"M2.2.4": note}))])
    recorder = ResultRecorder(tmp_path / "results.json", "pre")
    recorder.consume(report)
    tree, stats, _ = annotate({"title": "M2.2.4 重置"}, recorder.results)
    assert tree["notes"]["plain"]["content"].endswith(node)
    assert note in tree["notes"]["plain"]["content"]
    assert "限定范围通过" in tree["title"] and stats["limited_scope"] == 1
