"""Offline DOM checks; no PRE login or visible browser windows."""

import html

import pytest

from tests.metering_subscription_260901.helpers import (
    CHILD_HEADERS, PARENT_HEADERS, PARENT_HEADERS_UNIFIED, assert_entitlement_toggle,
    assert_headers_present, entitlement_rows,
)


@pytest.fixture(scope="module")
def offline_browser(playwright):
    browser = playwright.chromium.launch(headless=True)
    try:
        yield browser
    finally:
        browser.close()


@pytest.fixture
def dom_page(offline_browser):
    context = offline_browser.new_context()
    try:
        yield context.new_page()
    finally:
        context.close()


def table(headers, values, attrs=""):
    th = "".join(f"<th>{html.escape(header)}</th>" for header in headers)
    td = "".join(f"<td>{html.escape(value)}</td>" for value in values)
    return f"<table {attrs}><thead><tr>{th}</tr></thead><tbody><tr>{td}</tr></tbody></table>"


def test_menu_text_does_not_pass_table_contract(dom_page):
    dom_page.set_content("<nav>资源名称 服务模式 订阅应用</nav>" + table(("租户编码",), ("tenant",)))
    with pytest.raises(AssertionError, match="缺失表头"):
        assert_headers_present(dom_page, CHILD_HEADERS, "child")


def test_rows_are_read_from_child_not_parent_or_headers(dom_page):
    values = ("WPS服务组件", "应用接入申请", "应用1", "发布方", "2025-01-01", "永久有效",
              "不可用", "不限次数", "0", "不限次数", "查看订单明细")
    dom_page.set_content(table(PARENT_HEADERS, tuple("parent" for _ in PARENT_HEADERS)) + table(CHILD_HEADERS, values))
    rows = entitlement_rows(dom_page)
    assert len(rows) == 1 and rows[0]["可用状态"] == "不可用"
    assert rows[0]["总可调用额"] == rows[0]["剩余调用额"] == "不限次数"
    assert "parent" not in str(rows)


def test_header_only_table_cannot_prove_available_status(dom_page):
    dom_page.set_content(table(CHILD_HEADERS, ()))
    with pytest.raises(AssertionError, match="没有可核验"):
        entitlement_rows(dom_page)


def test_toggle_proves_child_is_shown_and_hidden_each_cycle(dom_page):
    parent = table(PARENT_HEADERS_UNIFIED, tuple("parent" for _ in PARENT_HEADERS_UNIFIED))
    action = '<a onclick="document.getElementById(\'child\').hidden = !document.getElementById(\'child\').hidden">查看</a>'
    parent = parent.replace("<td>parent</td></tr>", f"<td>{action}</td></tr>")
    dom_page.set_content(parent + table(CHILD_HEADERS, tuple("child" for _ in CHILD_HEADERS), 'id="child" hidden'))
    assert_entitlement_toggle(dom_page, cycles=3)
    assert not dom_page.locator("#child").is_visible()
