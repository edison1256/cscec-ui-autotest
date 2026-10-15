"""UI operations extracted from the 2026-10-13 black-box execution evidence."""

from __future__ import annotations

import re
import json
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urljoin, urlparse

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, expect

from core.metering_blackbox_contract import (
    ACCOUNT_HEADERS, CS_HEADERS, DAILY_HEADERS, ORDER_HEADERS, USAGE_HEADERS,
    WB_HEADERS, align_records, amount, assert_children, assert_daily_response, assert_metering_environment, require_data,
)

logger = logging.getLogger(__name__)


def visible(locator):
    result = locator.filter(visible=True).first
    result.wait_for(state="visible", timeout=25000)
    return result


def ui_table(scope, headers):
    candidates = []
    for table in scope.locator("table").all():
        if table.is_visible():
            actual = tuple(s.strip() for s in table.locator("thead").first.locator("th").all_text_contents())
            candidates.append(actual)
            if all(header in actual for header in headers):
                return table, actual
    raise AssertionError(f"缺少目标表格: {headers}; 实际表头: {candidates}")


def ui_rows(scope, headers):
    table, _ = ui_table(scope, headers)
    return table.evaluate("""t => {
        const hs = Array.from(t.tHead.rows[0].cells).map(c => c.innerText.trim());
        return Array.from(t.tBodies[0].rows)
          .filter(r => r.cells.length === hs.length && r.getClientRects().length &&
            Array.from(r.cells).some(c => c.innerText.trim()))
          .map(r => Object.fromEntries(Array.from(r.cells).map((c,i) => [hs[i], c.innerText.trim()])));
    }""")


def response_data(response):
    assert response.status == 200, f"业务请求HTTP状态异常: {response.status}"
    payload = response.json()
    assert payload.get("code") == 0, f"业务返回失败: code={payload.get('code')}"
    return payload["data"]


def watch_downloads(context):
    downloads = []
    def watch(page):
        page.on("download", lambda download: downloads.append(download))
    context.on("page", watch)
    for page in context.pages:
        watch(page)
    return downloads


def metering_route(page, root, profile, name, fragment):
    path = profile.get(name)
    if path:
        target = urljoin(root, path)
    else:
        links = page.locator("a[href]").evaluate_all("es => es.map(e => e.href)")
        matches = {link for link in links if fragment in link}
        require_data(len(matches) == 1, f"ROLE_REQUIRED: 当前页面无唯一生产路由，请在画像配置 {name}")
        target = matches.pop()
    assert_metering_environment(profile.get("environment", "pre"), target)
    return target


def component_list_response(response):
    return response.request.method == "POST" and urlparse(response.url).path.endswith(
        ("/component-portal/list", "/component-portal/my/list")
    )


def management_workbench_entry(page):
    entry = page.locator(".ant-popover.switch_propver").get_by_text("工作台", exact=True).filter(visible=True)
    expect(entry).to_have_count(1)
    return entry


class MeteringBlackboxPage:
    def __init__(self, page, domain: str, profile: dict):
        self.page = page
        self.domain = domain
        self.profile = profile
        self.headers = CS_HEADERS if domain == "cs" else ACCOUNT_HEADERS if domain in {"personal", "ordinary"} else WB_HEADERS
        self.endpoint = "aggregateForConsole" if domain == "cs" else "list" if domain in {"personal", "ordinary"} else "aggregate"
        self.responses = []
        self.last_data = None
        self.last_query = None
        self.scanned = []
        self.usage_summaries = []
        self.navigation = {}
        self.parent_bindings = {}
        self.last_expanded_raw = None
        page.on("response", lambda r: self.responses.append(r) if "/quota-" in r.url else None)

    def endpoint_response(self, response):
        return urlparse(response.url).path.endswith("/quota-instance/" + self.endpoint)

    def open(self, root: str, remember_portal=None):
        logger.info("[metering] open domain=%s", self.domain)
        assert_metering_environment(self.profile.get("environment", "pre"), root)
        self.page.goto(root, wait_until="domcontentloaded")
        if self.domain != "cs":
            name = self.profile["ordinary_tenant" if self.domain == "ordinary" else "admin_tenant"]
            user = visible(self.page.get_by_text(self.profile["display_name"], exact=True))
            labels = user.evaluate("e => [e, e.parentElement, e.parentElement.parentElement].map(n => n.innerText)")
            self.navigation = {"tenant": name, "user_labels": labels}
            if not any(name in label.splitlines() for label in labels):
                user.hover()
                visible(self.page.get_by_text("切换租户", exact=True)).click()
                choice = self.page.locator('[class*="tenant_item_text"]').filter(has_text=re.compile("^" + re.escape(name) + "$"))
                try:
                    visible(choice)
                except PlaywrightTimeoutError:
                    require_data(False, f"ROLE_REQUIRED: 租户选择器没有画像租户: {name}")
                visible(choice).click()
                expect(choice.filter(visible=True)).to_have_count(0, timeout=25000)
            expect(visible(self.page.get_by_text(name, exact=True))).to_be_visible()
            if self.domain != "ordinary":
                visible(self.page.get_by_text("管理后台", exact=True))
            self.page.goto(root, wait_until="domcontentloaded")
            expect(visible(self.page.get_by_text(name, exact=True))).to_be_visible()
            logger.info("[metering] tenant selected domain=%s", self.domain)
            if remember_portal is not None:
                remember_portal(self.page.context.storage_state())
            if self.domain == "ordinary":
                url = metering_route(self.page, root, self.profile, "personal_subscription_path", "/subscription/apiResource")
                self.page.goto(url, wait_until="domcontentloaded")
            else:
                visible(self.page.get_by_text("管理后台", exact=True)).hover()
                entry = management_workbench_entry(self.page)
                with self.page.context.expect_page() as popup:
                    entry.click()
                self.page = popup.value
                self.page.on("response", lambda r: self.responses.append(r) if "/quota-" in r.url else None)
        group, leaf = ("订阅服务", "API列表") if self.domain == "cs" else (
            ("我的订阅", "API订阅") if self.domain in {"personal", "ordinary"} else ("订阅中心", "API列表")
        )
        if self.domain != "ordinary":
            self.page.get_by_text(group, exact=True).filter(visible=True).first.wait_for(state="visible", timeout=60000)
            visible(self.page.get_by_text(group, exact=True)).click()
            visible(self.page.get_by_text(leaf, exact=True)).click()
        self.page.get_by_placeholder("请输入资源名称").filter(visible=True).first.wait_for(state="visible", timeout=60000)
        expect(self.page.locator("thead").get_by_text(self.headers[-2], exact=True).filter(visible=True).first).to_be_visible()
        return self.query(reset=True)

    def query(self, name="", code="", reset=False):
        logger.info("[metering] query domain=%s reset=%s", self.domain, reset)
        if not reset:
            visible(self.page.get_by_placeholder("请输入资源名称")).fill(name)
            if self.domain not in {"personal", "ordinary"}:
                visible(self.page.get_by_placeholder("请输入资源编码")).fill(code)
        with self.page.expect_request(lambda r: urlparse(r.url).path.endswith("/quota-instance/" + self.endpoint) and r.method == "POST") as info:
            visible(self.page.get_by_role("button", name="重 置" if reset else "查 询", exact=True)).click()
        response = info.value.response()
        assert response is not None, "当前查询没有业务响应"
        self.last_query = json.loads(info.value.post_data)
        self.last_data = self.sync(response_data(response))
        return self.last_data

    def sync(self, data):
        total = int(data["total"])
        expect(self.page.get_by_text(re.compile(r"第.*总共\s*" + str(total) + r"\s*条")).filter(visible=True).last).to_be_visible()
        if data["list"]:
            table, _ = ui_table(self.page, self.headers)
            fields = {"资源名称": "resourceName", "服务模式": "serviceModeName", "订阅应用": "applyAppName"} if self.domain in {"personal", "ordinary"} else {"资源编码": "resourceCode", "服务模式": "serviceModeName"}
            if self.domain == "cs":
                fields["租户编码"] = "tenantNo"
            for record in data["list"]:
                row = table.locator("tbody").first.locator(":scope > tr")
                for key in fields.values():
                    row = row.filter(has=self.page.get_by_text(str(record[key]), exact=True))
                expect(row.first).to_be_visible(timeout=20000)
            records = align_records(ui_rows(self.page, self.headers), data["list"], fields, allow_ambiguous=self.domain not in {"personal", "ordinary"})
        else:
            expect(ui_table(self.page, self.headers)[0].get_by_text("暂无数据", exact=True)).to_be_visible()
            records = []
        assert len(ui_rows(self.page, self.headers)) == len(data["list"]), "页面行数与本次查询响应不一致"
        self.parent_bindings = {}
        return {**data, "list": records}

    def row_locator(self, index):
        table, _ = ui_table(self.page, self.headers)
        marker = "查看订单明细" if self.domain in {"personal", "ordinary"} else re.compile(r"^\s*(查看|收起)\s*$")
        return table.locator("tbody").first.locator(":scope > tr").filter(has=self.page.get_by_text(marker, exact=isinstance(marker, str))).nth(index)

    def page_to(self, index):
        li = visible(self.page.locator(f'li[title="{index}"]'))
        if "ant-pagination-item-active" not in (li.get_attribute("class") or ""):
            with self.page.expect_response(self.endpoint_response) as info:
                li.click()
            expect(li).to_have_class(re.compile("ant-pagination-item-active"))
            self.last_data = self.sync(response_data(info.value))
        return self.last_data

    def expand(self, index=0):
        require_data(bool(self.last_data["list"]), "聚合列表没有正向账户")
        parent = ui_rows(self.page, self.headers)[index]
        row = self.row_locator(index)
        action = row.locator(":scope > td").last.get_by_role("button").first
        binding = self.parent_bindings.get(index)
        same_label = [r for r in self.last_data["list"] if r["resourceCode"] == parent["资源编码"]
                      and r["serviceModeName"] == parent["服务模式"]
                      and (self.domain != "cs" or r["tenantNo"] == parent["租户编码"])]
        if binding is None and len(same_label) == 1:
            binding = same_label[0]
        ids = {str(value) for value in binding["instanceIds"]} if binding else None
        def current_response(response):
            if not urlparse(response.url).path.endswith("/quota-instance/listByIds"):
                return False
            request = json.loads(response.request.post_data or "{}")
            return isinstance(request, dict) and ids is not None and {str(value) for value in request.get("instanceIds", [])} == ids
        cached = next((r for r in reversed(self.responses) if current_response(r)), None) if binding else None
        if action.inner_text().strip() == "查看":
            if cached is None:
                with self.page.expect_request(lambda r: urlparse(r.url).path.endswith("/quota-instance/listByIds") and r.method == "POST") as info:
                    action.click()
                cached = info.value.response()
            else:
                action.click()
        assert cached is not None, "没有当前父行ID集合对应的本轮业务响应"
        request_ids = {str(value) for value in json.loads(cached.request.post_data)["instanceIds"]}
        matches = [r for r in same_label if {str(value) for value in r["instanceIds"]} == request_ids]
        assert len(matches) == 1, "展开请求不能唯一对应当前父行的实例集合"
        raw = matches[0]
        self.parent_bindings[index] = raw
        self.last_expanded_raw = raw
        accounts = response_data(cached)
        expect(action).to_have_text("收起")
        panel = row.locator("xpath=following-sibling::tr[1]")
        expect(panel.locator("thead").get_by_text("总可调用额", exact=True).first).to_be_visible()
        if accounts:
            expect(panel.get_by_text("查看订单明细", exact=True).filter(visible=True).first).to_be_visible(timeout=20000)
        else:
            expect(panel.get_by_text("暂无数据", exact=True)).to_be_visible(timeout=20000)
        children = ui_rows(panel, ACCOUNT_HEADERS)
        assert_children(parent, children, raw, accounts)
        return row, panel, accounts

    def collapse(self, row):
        row.locator(":scope > td").last.get_by_role("button").first.click()
        expect(row.locator("xpath=following-sibling::tr[1]")).to_be_hidden()
        expect(row.locator(":scope > td").last.get_by_role("button").first).to_have_text("查看")

    def scan(self):
        data = self.query(reset=True)
        total = int(data["total"])
        require_data(total > 0, "缺少聚合账户数据")
        page_size = len(data["list"])
        self.scanned = []
        observations = self.scanned
        for number in range(1, (total + page_size - 1) // page_size + 1):
            logger.info("[metering] scan domain=%s page=%s total=%s", self.domain, number, total)
            if number > 1:
                data = self.page_to(number)
            for index in range(len(data["list"])):
                row, panel, accounts = self.expand(index)
                assert ui_table(panel, ACCOUNT_HEADERS)[1] == ACCOUNT_HEADERS
                observations.append({"parent": ui_rows(self.page, self.headers)[index], "raw": self.last_expanded_raw,
                                     "accounts": accounts, "ui": ui_rows(panel, ACCOUNT_HEADERS)})
                self.collapse(row)
        assert len(observations) == total, "扫描未覆盖全部父行"
        keys = [(x["raw"]["tenantNo"], x["raw"]["resourceId"], x["raw"]["serviceMode"]) for x in observations]
        assert len(set(keys)) == total, "租户/资源/服务模式组合重复"
        return observations

    def sample_account(self, prefer_largest=False):
        data = self.query(reset=True)
        require_data(bool(data["list"]), "本轮没有可用计量样本")
        size, total = len(data["list"]), int(data["total"])
        for number in range(1, (total + size - 1) // size + 1):
            if number > 1:
                data = self.page_to(number)
            candidates = []
            for index in range(len(data["list"])):
                parent, panel, accounts = self.expand(index)
                target = next((a for a in accounts if amount(str(a["usedQuota"])) > 0), None)
                if target:
                    if not prefer_largest:
                        row = panel.get_by_text(target["applyAppName"], exact=True).locator("xpath=ancestor::tr[1]")
                        return row, target
                    candidates.extend((index, account) for account in accounts if amount(str(account["usedQuota"])) > 0)
                self.collapse(parent)
            if candidates:
                index, target = max(candidates, key=lambda item: amount(str(item[1]["usedQuota"])))
                _, panel, _ = self.expand(index)
                row = panel.get_by_text(target["applyAppName"], exact=True).locator("xpath=ancestor::tr[1]")
                return row, target
        require_data(False, "本轮账户均无正向调用数据，不能用零值证明累计一致性")

    def usage(self, row, positive=False, account=None):
        allowed_ids = {str(value) for value in account["instanceIds"]} | {str(account["id"])} if account is not None else None
        def current_response(response):
            if not urlparse(response.url).path.endswith("/quota-daily/listSummary"):
                return False
            ids = json.loads(response.request.post_data or "[]")
            return isinstance(ids, list) and bool(ids) and (allowed_ids is None or {str(value) for value in ids} <= allowed_ids)
        cached = next((r for r in reversed(self.responses) if current_response(r)), None)
        if cached is None:
            with self.page.expect_response(current_response) as info:
                visible(row.get_by_text("查看用量", exact=True)).click()
            cached = info.value
        else:
            visible(row.get_by_text("查看用量", exact=True)).click()
        self.usage_summaries = response_data(cached)
        panel = row.locator("xpath=following-sibling::tr[1]")
        expect(panel.locator("thead").get_by_text("接口名称", exact=True)).to_be_visible()
        if positive:
            expect(panel.get_by_text("查看明细", exact=True).filter(visible=True).first).to_be_visible(timeout=20000)
        assert ui_table(panel, USAGE_HEADERS)[1] == USAGE_HEADERS
        records = ui_rows(panel, USAGE_HEADERS)
        expected = {}
        for summary in self.usage_summaries:
            name = summary["eipApiName"]
            expected[name] = expected.get(name, 0) + amount(str(summary["sumCallQuota"]))
        assert len(records) == len(expected), "接口行重复或数量与当前用量汇总响应不一致"
        assert {record["接口名称"]: amount(record["已调用额"]) for record in records} == expected, "接口累计与本轮用量汇总响应不一致"
        return panel, records

    def orders(self, row, account=None):
        current = None
        if account is not None:
            ids = {str(value) for value in account["orderIds"]}
            def is_current(response):
                if not urlparse(response.url).path.endswith("/quota-instance-order/findByOrderIds"):
                    return False
                request_ids = json.loads(response.request.post_data or "[]")
                return isinstance(request_ids, list) and {str(value) for value in request_ids} == ids
            with self.page.expect_response(is_current) as info:
                visible(row.get_by_text("查看订单明细", exact=True)).click()
            current = response_data(info.value)
        else:
            visible(row.get_by_text("查看订单明细", exact=True)).click()
        dialog = self.page.get_by_role("dialog").filter(visible=True).last
        expect(dialog.get_by_text("订单明细", exact=True)).to_be_visible()
        expect(dialog.locator("thead").get_by_text("订单ID", exact=True)).to_be_visible()
        if account is not None and account["orderIds"]:
            expect(dialog.get_by_text("详情", exact=True).filter(visible=True).first).to_be_visible(timeout=20000)
        fields = ("订单ID", "订阅人", "生效时间", "操作")
        self.order_headers = ui_table(dialog, fields)[1]
        text = visible(dialog.get_by_text(re.compile(r"第.*总共\s*\d+\s*条"))).inner_text()
        total = int(re.search(r"总共\s*(\d+)\s*条", text).group(1))
        records = ui_rows(dialog, fields)
        if records:
            size = len(records)
            for number in range(2, (total + size - 1) // size + 1):
                self.order_page(dialog, number)
                records.extend(ui_rows(dialog, fields))
            if total > size:
                self.order_page(dialog, 1)
        assert len(records) == total, "订单明细未读取全部分页"
        if account is not None:
            matching = current
            assert len(matching) == len(ids), "订单响应重复或缺失当前账户的订单ID"
            assert {str(order["orderId"]) for order in matching} == ids
            assert {order["orderCode"] for order in matching} == {order["订单ID"] for order in records}
            assert len(records) == len(matching), "订单UI重复或缺失"
            assert len({order["订单ID"] for order in records}) == len(records), "订单UI出现重复订单编码"
        return dialog, records

    def order_page(self, dialog, number):
        li = visible(dialog.locator(f'li[title="{number}"]'))
        if "ant-pagination-item-active" not in (li.get_attribute("class") or ""):
            fields = ("订单ID", "订阅人", "生效时间", "操作")
            before = ui_rows(dialog, fields)[0]["订单ID"]
            li.click()
            expect(li).to_have_class(re.compile("ant-pagination-item-active"))
            expect(ui_table(dialog, fields)[0].get_by_text(before, exact=True)).to_be_hidden()

    def form_field(self, label):
        return self.page.get_by_role("dialog").filter(visible=True).last.get_by_text(label, exact=True).locator(
            'xpath=ancestor::div[contains(concat(" ",normalize-space(@class)," ")," ant-form-item ")][1]'
        ).locator("input").first

    def order_form(self, order):
        dialog = self.page.get_by_role("dialog").filter(visible=True).last
        if not dialog.get_by_text(order["订单ID"], exact=True).filter(visible=True).count():
            numbers = [int(value) for value in dialog.locator("li[title]").evaluate_all(
                "es => es.map(e => e.getAttribute('title')).filter(v => /^\\d+$/.test(v))"
            )]
            for number in sorted(set(numbers)):
                self.order_page(dialog, number)
                if dialog.get_by_text(order["订单ID"], exact=True).filter(visible=True).count():
                    break
        dialog.get_by_text(order["订单ID"], exact=True).locator("xpath=ancestor::tr[1]").get_by_text("详情", exact=True).click()
        expect(self.form_field("订单编码")).to_have_value(order["订单ID"])
        fields = {label: self.form_field(label).input_value() for label in (
            "订单编码", "订单状态", "创建人ID", "资源名称", "服务模式", "租户名"
        )}
        fields["text"] = self.page.get_by_role("dialog").filter(visible=True).last.inner_text()
        fields["api_paths"] = self.page.get_by_role("dialog").filter(visible=True).last.get_by_text(
            re.compile(r"^/api/")
        ).filter(visible=True).all_text_contents()
        visible(self.page.get_by_role("button", name="返 回", exact=True)).click()
        expect(self.page.get_by_role("dialog").filter(visible=True).last.get_by_text("订单明细", exact=True)).to_be_visible()
        return fields

    def close_dialog(self):
        dialog = self.page.get_by_role("dialog").filter(visible=True).last
        close = dialog.get_by_role("button", name="Close", exact=True).filter(visible=True)
        if close.count():
            close.first.click()
        else:
            dialog.locator('[data-icon="close"]').last.click()
        self.page.mouse.move(500, 300)
        expect(dialog).to_be_hidden()

    def daily(self, usage_panel, index=0, require_pagination=False):
        records = ui_rows(usage_panel, USAGE_HEADERS)
        require_data(len(records) > index, "缺少接口用量正向数据")
        table, _ = ui_table(usage_panel, USAGE_HEADERS)
        summaries = [s for s in self.usage_summaries if s["eipApiName"] == records[index]["接口名称"]]
        def current_detail(response):
            parsed = urlparse(response.url)
            if not parsed.path.endswith("/quota-daily/detail"):
                return False
            query = parse_qs(parsed.query)
            return any(query.get("quotaInstanceId") == [str(s["quotaInstanceId"])] and query.get("eipApiId") == [str(s["eipApiId"])] for s in summaries)
        with self.page.expect_response(current_detail) as info:
            table.locator("tbody").first.locator(":scope > tr").filter(
                has=self.page.get_by_text("查看明细", exact=True)
            ).nth(index).get_by_text("查看明细", exact=True).click()
        data = response_data(info.value)
        dialog = self.page.get_by_role("dialog").filter(visible=True).last
        expect(dialog.locator("thead").get_by_text("日期", exact=True)).to_be_visible()
        assert ui_table(dialog, DAILY_HEADERS)[1] == DAILY_HEADERS
        expect(dialog.get_by_text(re.compile(r"^\d{4}-\d{2}-\d{2}$")).filter(visible=True).first).to_be_visible(timeout=20000)
        text = visible(dialog.get_by_text(re.compile(r"第.*总共\s*\d+\s*条"))).inner_text()
        total = int(re.search(r"总共\s*(\d+)\s*条", text).group(1))
        require_data(total > 0, "当前接口没有日明细数据")
        page_size = len(ui_rows(dialog, DAILY_HEADERS))
        require_data(page_size > 0, "当前接口没有日明细数据")
        if require_pagination:
            require_data(total > page_size, "当前计量样本没有第二页，不将单页读取算作分页验证通过")
        result = []
        for number in range(1, (total + page_size - 1) // page_size + 1):
            if number > 1:
                before = ui_rows(dialog, DAILY_HEADERS)[0]["日期"]
                li = visible(dialog.locator(f'li[title="{number}"]'))
                li.click()
                expect(li).to_have_class(re.compile("ant-pagination-item-active"))
                expect(ui_table(dialog, DAILY_HEADERS)[0].get_by_text(before, exact=True)).to_be_hidden()
                expect(dialog.get_by_text(re.compile(r"^\d{4}-\d{2}-\d{2}$")).filter(visible=True).first).to_be_visible()
            result.extend(ui_rows(dialog, DAILY_HEADERS))
        assert_daily_response(result, data)
        return dialog, result, total, records[index]["已调用额"]

    def subscription_dates(self, start, end):
        inputs = self.page.get_by_placeholder("请选择时间").filter(visible=True)
        inputs.first.hover()
        clear = self.page.locator(".ant-picker-clear").filter(visible=True)
        if clear.count():
            clear.first.click()
        for index, value in enumerate((start, end)):
            inputs.nth(index).fill(value)
            inputs.nth(index).press("Enter")
        visible(self.page.get_by_text("订阅时间", exact=True)).click()
        assert inputs.evaluate_all("es => es.map(e => e.value)") == [start, end]

    def component_list(self):
        visible(self.page.get_by_text("组件列表", exact=True)).click()
        visible(self.page.get_by_placeholder("请输入资源名称"))
        with self.page.expect_response(lambda r: urlparse(r.url).path.endswith("/compt/apply/history/list") and r.request.method == "POST") as info:
            visible(self.page.get_by_role("button", name="查 询", exact=True)).click()
        data = response_data(info.value)
        expect(self.page.get_by_text("订阅ID", exact=True).filter(visible=True).first).to_be_visible(timeout=20000)
        require_data(bool(data["list"]), "缺少通用订阅回归正向数据")
        for record in data["list"]:
            expect(self.page.get_by_text(str(record["id"]), exact=True).filter(visible=True).first).to_be_visible()
        expect(self.page.get_by_text("订阅人", exact=True).filter(visible=True).first).to_be_visible()
        text = self.page.locator("body").inner_text()
        assert "总可调用额" not in text and "剩余调用额" not in text
        self.component_data = data

    @staticmethod
    def future_dates():
        today = datetime.now(timezone(timedelta(hours=8))).date()
        return str(today + timedelta(days=3650)), str(today + timedelta(days=3651))
