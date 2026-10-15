"""Current-run UI proofs; a workflow can cover several original outline items."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from decimal import Decimal
from uuid import uuid4
from urllib.parse import urlparse

import pytest
from playwright.sync_api import expect

from core.metering_blackbox_contract import (
    ACCOUNT_HEADERS, CS_HEADERS, ORDER_HEADERS, USAGE_HEADERS, WB_HEADERS, MissingMeteringData,
    amount, assert_daily, assert_export, load_manifest, require_data,
)
from pages.metering_blackbox_page import component_list_response, metering_route, response_data, ui_rows, ui_table, visible, watch_downloads

MANIFEST = load_manifest()
pytestmark = [pytest.mark.metering_blackbox_verified, pytest.mark.regression]


def matching(model, name="", code=""):
    data = model.query(name=name, code=code)
    require_data(bool(data["list"]), "缺少指定查询的成功订阅正向样本")
    records = ui_rows(model.page, model.headers)
    assert all(not name or name in row["资源名称"] for row in records)
    assert all(not code or code == row["资源编码"] for row in records)
    return data


def query_workflow(provider, key):
    model = provider.get("cs" if key.startswith("cs_") else "wb")
    baseline = model.last_data
    baseline_query = model.last_query
    require_data(bool(baseline["list"]), "当前列表无查询正向样本")
    resource = provider.profile.get("query_resource")
    if not resource:
        counts = Counter(row["resourceName"] for row in baseline["list"])
        resource = counts.most_common(1)[0][0] if key == "wb_modes" else baseline["list"][0]["resourceName"]
    if key.endswith("_code"):
        data = matching(model, code=baseline["list"][0]["resourceCode"])
    elif key.endswith("_name") or key == "wb_modes":
        data = matching(model, name=resource)
        if key == "wb_modes":
            require_data(len({row["serviceMode"] for row in data["list"]}) > 1, "指定资源没有多服务模式样本")
            assert len({(row["resourceId"], row["serviceMode"]) for row in data["list"]}) == len(data["list"])
    elif key == "wb_combo":
        target = baseline["list"][0]
        data = matching(model, name=target["resourceName"], code=target["resourceCode"])
        other = next((row for row in baseline["list"] if row["resourceCode"] != target["resourceCode"]), None)
        require_data(other is not None, "组合筛选缺少第二个不同资源编码反例")
        assert int(model.query(name=target["resourceName"], code=other["resourceCode"])["total"]) == 0
    elif key.endswith("_reset"):
        model.query(name="__metering_missing_" + uuid4().hex)
        if model.domain == "cs":
            start, end = model.future_dates()
            model.subscription_dates(start, end)
            model.query(name="__metering_missing_" + uuid4().hex)
        data = model.query(reset=True)
        assert model.last_query["queryfilter"] == baseline_query["queryfilter"], "重置请求仍残留筛选条件"
        for placeholder in ("请输入资源名称", "请输入资源编码"):
            assert visible(model.page.get_by_placeholder(placeholder)).input_value() == ""
        if model.domain == "cs":
            assert model.page.get_by_placeholder("请选择时间").filter(visible=True).evaluate_all("es => es.map(e => e.value)") == ["", ""]
    else:
        missing = "__metering_missing_" + uuid4().hex
        data = model.query(code=missing)
        assert data["list"] == [] and int(data["total"]) == 0
    provider.observations[key] = {"baseline_total": baseline["total"], "current_response": data,
                                  "ui": ui_rows(model.page, model.headers)}


def own_orders(model, username):
    data = model.query(reset=True)
    require_data(bool(data["list"]), "当前本人没有成功权益账户")
    total, size = int(data["total"]), len(data["list"])
    result = []
    for number in range(1, (total + size - 1) // size + 1):
        if number > 1:
            data = model.page_to(number)
        accounts = ui_rows(model.page, ACCOUNT_HEADERS)
        for index, account in enumerate(accounts):
            _, orders = model.orders(model.row_locator(index), data["list"][index])
            require_data(bool(orders), "本人权益没有可核验的成功订单")
            forms = [model.order_form(order) for order in orders]
            assert all(form["创建人ID"] == username and form["订单状态"] == "订阅成功" for form in forms)
            assert all(form["资源名称"] == account["资源名称"] and form["服务模式"] == account["服务模式"] for form in forms)
            result.append({"account": account, "raw": data["list"][index], "forms": forms})
            model.close_dialog()
    assert len(result) == total, "本人订单验证未覆盖全部账户分页"
    return result


def assert_no_write(scope):
    forbidden = {"续订", "变配", "增购", "购买", "立即购买", "编辑", "删除", "编辑权益", "删除权益", "修改额度", "编辑API范围"}
    for control in scope.locator("button, a, [role='button'], [role='menuitem']").all():
        if control.is_visible():
            label = control.get_attribute("aria-label") or control.inner_text()
            assert re.sub(r"\s+", "", label) not in forbidden, "只读权益链路出现业务修改入口"


def usage_workflow(provider, key):
    model = provider.get("cs" if key == "cs_readonly" else "wb")
    row, raw = model.sample_account(prefer_largest=key == "daily_pagination")
    provider.observations["account"] = raw
    if key in {"wb_orders", "wb_order_columns", "cs_orders"}:
        _, orders = model.orders(row, raw)
        require_data(bool(orders), "当前权益没有成功订阅订单")
        forms = [model.order_form(order) for order in orders]
        provider.observations["order_headers"] = model.order_headers
        if key == "wb_order_columns":
            assert model.order_headers == ORDER_HEADERS, f"CONTRACT_DIFFERENCE: 2026-10-15确认的订单字段为{ORDER_HEADERS}，当前字段为{model.order_headers}"
        assert all(form["资源名称"] == raw["resourceName"] and form["订单状态"] == "订阅成功" for form in forms)
        assert all(form["服务模式"] == raw["serviceModeName"] for form in forms)
        provider.observations["orders"] = {"ui": orders, "forms": forms}
        return
    panel, records = model.usage(row, positive=True, account=raw)
    require_data(bool(records), "账户有用量但缺少可核验接口正向样本")
    assert ui_table(panel, USAGE_HEADERS)[1] == USAGE_HEADERS
    account_ui = dict(zip(ACCOUNT_HEADERS, (cell.inner_text().strip() for cell in row.locator(":scope > td").all())))
    for record in records:
        amount(record["已调用额"])
    used = amount(account_ui["已调用额"])
    assert used == amount(str(raw["usedQuota"])), "账户页面累计与当前业务响应不一致"
    assert sum((amount(record["已调用额"]) for record in records), Decimal(0)) == used, "接口累计合计与当前账户累计不一致"
    provider.observations["account_ui"] = account_ui
    provider.observations["usage"] = records
    positive_index = max(range(len(records)), key=lambda index: amount(records[index]["已调用额"]))
    if key == "wb_usage":
        visible(row.get_by_text("收起用量", exact=True)).click()
        expect(panel).to_be_hidden()
        reopened, records_again = model.usage(row, positive=True, account=raw)
        assert Counter(r["接口名称"] for r in records_again) == Counter(r["接口名称"] for r in records), "收起/重开后接口身份变化或重复"
        assert_no_write(reopened)
    elif key == "rapid_usage":
        for _ in range(9):
            visible(row.get_by_text("收起用量", exact=True)).click()
            expect(panel).to_be_hidden()
            panel, current = model.usage(row, positive=True, account=raw)
            assert Counter(r["接口名称"] for r in current) == Counter(r["接口名称"] for r in records), "连续用量展开出现重复插入或串账户"
    elif key == "cs_readonly":
        assert_no_write(ui_table(model.page, model.headers)[0])
        assert_no_write(row)
        assert_no_write(panel)
        dialog, days, total, used = model.daily(panel, index=positive_index)
        assert_daily(days, total, used)
        assert_no_write(dialog)
        model.close_dialog()
        dialog, _ = model.orders(row, raw)
        assert_no_write(dialog)
    else:
        _, days, total, used = model.daily(panel, index=positive_index, require_pagination=key == "daily_pagination")
        if key == "daily":
            require_data(total > 1, "当前样本只有一天，不能证明多天日期倒序")
        assert_daily(days, total, used)
        provider.observations["daily"] = {"rows": days, "total": total, "interface_used": used}


def export_workflow(provider):
    if provider.profile.get("environment") == "prod":
        raise AssertionError("WRITE_BLOCKED: production export creates asynchronous tasks")
    model = provider.get("cs")
    row, raw = model.sample_account()
    panel, records = model.usage(row, positive=True, account=raw)
    positive_index = max(range(len(records)), key=lambda index: amount(records[index]["已调用额"]))
    dialog, days, total, used = model.daily(panel, index=positive_index)
    assert_daily(days, total, used)
    start, end = min(day["日期"] for day in days), max(day["日期"] for day in days)
    dialog.get_by_placeholder("开始日期").hover()
    clear = dialog.locator(".ant-picker-clear").filter(visible=True)
    if clear.count():
        clear.first.click()
    for placeholder, value in (("开始日期", start), ("结束日期", end)):
        dialog.get_by_placeholder(placeholder).fill(value)
        dialog.get_by_placeholder(placeholder).press("Enter")
    visible(dialog.get_by_text("日期区间", exact=True)).click()
    assert [dialog.get_by_placeholder(name).input_value() for name in ("开始日期", "结束日期")] == [start, end]
    context = model.page.context
    downloads = watch_downloads(context)
    saved = []
    for number in range(2):
        previous = len(downloads)
        with context.expect_page(timeout=45000) as info:
            visible(dialog.get_by_role("button", name="导 出", exact=True)).click()
        popup = info.value
        download = downloads[-1] if len(downloads) > previous else popup.wait_for_event("download", timeout=45000)
        assert download.failure() is None, "导出任务未取得实际CSV文件"
        path = provider.output_dir / f"download-{number + 1}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        download.save_as(str(path))
        blob = path.read_bytes()
        saved.append({"file": str(path), "suggested_filename": download.suggested_filename,
                      "sha256": hashlib.sha256(blob).hexdigest(), **assert_export(blob, days)})
        popup.close()
    expect(visible(dialog.get_by_role("button", name="查 询", exact=True))).to_be_enabled()
    provider.observations["export"] = {"range": [start, end], "daily_total": total, "downloads": saved,
                                      "byte_identical": saved[0]["sha256"] == saved[1]["sha256"],
                                      "scope": "重复导出稳定性；文件名/重复BOM历史缺陷单独记录，不判已修复"}


def run_workflow(provider, key):
    if key in {"wb_modes", "wb_code", "wb_name", "wb_combo", "wb_reset", "wb_empty", "cs_name", "cs_code", "cs_reset"}:
        return query_workflow(provider, key)
    if key in {"wb_usage", "rapid_usage", "daily", "daily_pagination", "cs_readonly", "wb_orders", "wb_order_columns"}:
        return usage_workflow(provider, key)
    if key == "cs_orders":
        model = provider.get("cs")
        row, raw = model.sample_account()
        _, orders = model.orders(row, raw)
        require_data(bool(orders), "当前控制台账户没有成功订单")
        forms = [model.order_form(order) for order in orders]
        assert all(form["资源名称"] == raw["resourceName"] and form["订单状态"] == "订阅成功" for form in forms)
        provider.observations["orders"] = forms
    elif key in {"wb_entry", "cs_entry", "wb_default", "wb_columns", "cs_legacy"}:
        model = provider.get("cs" if key.startswith("cs_") else "wb")
        require_data(bool(model.last_data["list"]), "缺少聚合列表正向样本")
        actual = ui_table(model.page, model.headers)[1]
        assert set(actual) == set(model.headers)
        if key == "wb_default":
            assert actual == WB_HEADERS
            assert model.page.get_by_text("查看订单明细", exact=True).filter(visible=True).count() == 0
        if key == "wb_columns":
            assert actual == WB_HEADERS, f"CONTRACT_DIFFERENCE: 2026-10-15确认的父表字段为{WB_HEADERS}，当前字段为{actual}"
        if key == "cs_legacy":
            assert not set(actual) & {"订阅ID", "订阅资源名称", "订阅人"}
        provider.observations[key] = {"ui_headers": actual, "response": model.last_data}
    elif key in {"wb_component", "cs_component"}:
        provider.get("cs" if key.startswith("cs_") else "wb").component_list()
    elif key == "scan":
        results = {domain: provider.get(domain).scan() for domain in ("wb", "cs")}
        require_data(any(len({row["订阅应用"] for row in item["ui"]}) > 1 for item in results["wb"]), "缺少同资源同模式多应用账户样本")
        provider.observations["all_parents"] = results
    elif key in {"wb_toggle", "rapid_parent"}:
        model = provider.get("wb")
        require_data(bool(model.last_data["list"]), "缺少父行展开样本")
        before = None
        for _ in range(10 if key == "rapid_parent" else 1):
            row, panel, _ = model.expand()
            current = ui_rows(panel, ACCOUNT_HEADERS)
            if before is not None:
                identity = lambda rows: Counter((r["资源名称"], r["服务模式"], r["订阅应用"]) for r in rows)
                assert identity(current) == identity(before), "连续展开子表账户身份变化或重复"
            before = current
            model.collapse(row)
        provider.observations["accounts"] = before
    elif key == "personal_default":
        for domain in ("personal", "ordinary"):
            model = provider.get(domain)
            assert ui_table(model.page, ACCOUNT_HEADERS)[1] == ACCOUNT_HEADERS
            selection = model.page.locator(".ant-select-selection-item").filter(visible=True).all_text_contents()
            assert "可用" in selection, "可用不是筛选控件的选中值"
            text = ui_table(model.page, ACCOUNT_HEADERS)[0].inner_text().lower()
            assert not any(token in text for token in ("aksk", "secretkey", "secret_key"))
            provider.observations[domain] = {"selection": selection, "rows": ui_rows(model.page, ACCOUNT_HEADERS)}
    elif key in {"personal_owners", "personal_merge", "multi_api"}:
        if key == "personal_owners":
            provider.get("wb")
        model = provider.get("personal")
        proof = own_orders(model, provider.profile["username"])
        if key == "personal_merge":
            candidates = [item for item in proof if len(item["forms"]) > 1]
            require_data(bool(candidates), "缺少本人同资源/应用/模式多次成功订阅样本")
            keys = [(item["account"]["资源名称"], item["account"]["订阅应用"], item["account"]["服务模式"]) for item in proof]
            assert len(keys) == len(set(keys)), "本人相同资源/应用/模式未合并"
        if key == "multi_api":
            candidates = [item for item in proof if any(len(set(form["api_paths"])) > 1 for form in item["forms"])]
            require_data(bool(candidates), "缺少单订单包含多个API的当前成功订阅样本")
            admin = provider.get("wb")
            observations = admin.scan()
            for item in candidates:
                matching_accounts = [entry for entry in observations if entry["parent"]["资源名称"] == item["account"]["资源名称"]
                                     and entry["parent"]["服务模式"] == item["account"]["服务模式"]]
                require_data(bool(matching_accounts), "管理员视图无本人账户对应父行")
                assert any(sum(row["订阅应用"] == item["account"]["订阅应用"] for row in entry["ui"]) == 1 for entry in matching_accounts)
        provider.observations["own_orders"] = proof
    elif key == "personal_permanent":
        model = provider.get("personal")
        data = model.last_data
        require_data(bool(data["list"]), "缺少本人永久有效权益")
        matches = [row for row in ui_rows(model.page, ACCOUNT_HEADERS) if row["截止时间"] == "永久有效"]
        require_data(bool(matches), "当前本人没有永久有效账户")
        provider.observations["permanent"] = matches
    elif key == "cs_dates":
        model = provider.get("cs")
        account, raw = model.sample_account()
        _, orders = model.orders(account, raw)
        require_data(bool(orders), "缺少日期筛选的成功订单对照")
        known = orders[0]["生效时间"][:10]
        model.close_dialog()
        model.subscription_dates(known, known)
        data = model.query(name=raw["resourceName"])
        assert any(parent["resourceId"] == raw["resourceId"] and parent["serviceMode"] == raw["serviceMode"] for parent in data["list"]), "同日订阅时间筛选遗漏当前已知成功订单的资源/模式"
        start, end = model.future_dates()
        model.subscription_dates(start, end)
        future = model.query(name=raw["resourceName"])
        assert int(future["total"]) == 0, "超出本轮当前成功订单日期的未来区间仍有匹配"
        provider.observations["dates"] = {"known_order": orders[0], "known_day_response": data, "future_response": future}
    elif key == "delivery":
        model = provider.get("wb")
        origin = urlparse(model.page.url)
        url = metering_route(model.page, f"{origin.scheme}://{origin.netloc}/", provider.profile,
                             "resource_catalog_path", "/resource/comp")
        model.page.goto(url, wait_until="domcontentloaded")
        expect(model.page.get_by_text("交付方式", exact=True).filter(visible=True).first).to_be_visible(timeout=20000)
        with model.page.expect_response(component_list_response) as info:
            visible(model.page.get_by_role("button", name="查 询", exact=True)).click()
        before = response_data(info.value)["list"]
        require_data(any(row["typeName"] == "API" for row in before), "缺少API交付方式正向资源")
        for row in before:
            expect(model.page.get_by_text(row.get("resourceCode") or row["name"], exact=True).filter(visible=True).first).to_be_visible()
        selection = model.page.get_by_text("请选择组件类型", exact=True).locator('xpath=ancestor::div[contains(@class,"ant-select")][1]')
        selection.get_by_role("combobox").click()
        option = model.page.locator(".ant-select-item-option").filter(has_text=re.compile("^SDK$"))
        visible(option).click()
        with model.page.expect_response(component_list_response) as info:
            visible(model.page.get_by_role("button", name="查 询", exact=True)).click()
        after = response_data(info.value)["list"]
        require_data(bool(after), "缺少SDK资源正向样本")
        assert all(row["typeName"] == "SDK" for row in after)
        for row in after:
            expect(model.page.get_by_text(row.get("resourceCode") or row["name"], exact=True).filter(visible=True).first).to_be_visible()
        expect(model.page.get_by_text("SDK", exact=True).filter(visible=True).first).to_be_visible()
        provider.observations["delivery"] = {"before": before, "after": after}
    elif key == "repeat_export":
        export_workflow(provider)
    elif key == "sensitive":
        for domain in ("wb", "cs", "personal"):
            model = provider.get(domain)
            table, _ = ui_table(model.page, model.headers)
            text = table.inner_text().lower()
            if domain != "personal" and model.last_data["list"]:
                _, panel, accounts = model.expand()
                text += panel.inner_text().lower()
                table, _ = ui_table(panel, ACCOUNT_HEADERS)
                row = table.locator("tbody").first.locator(":scope > tr").filter(
                    has=model.page.get_by_text(accounts[0]["applyAppName"], exact=True)
                ).first
                usage, _ = model.usage(row, account=accounts[0])
                text += usage.inner_text().lower()
            assert not any(token in text for token in ("aksk", "secretkey", "secret_key", "accesskey"))
    else:
        raise AssertionError(f"未实现的workflow不能视为通过: {key}")


@pytest.mark.parametrize("scenario", [
    pytest.param(scenario, id=scenario["key"],
                 marks=pytest.mark.write if scenario.get("requires_export") else pytest.mark.readonly)
    for scenario in MANIFEST["scenarios"]
])
def test_verified_workflow(scenario, blackbox_pages):
    """Execute the declared workflow independently; derive all values in this run."""
    try:
        run_workflow(blackbox_pages, scenario["key"])
    except MissingMeteringData as exc:
        pytest.skip(f"DATA_REQUIRED: {exc}")
