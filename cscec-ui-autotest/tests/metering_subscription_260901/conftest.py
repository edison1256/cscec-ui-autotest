"""Local fixtures for metering_subscription_260901 PRE coverage.

Provides module-scoped logged-in pages for both split domains plus a
session-wide case-result recorder consumed by the outline generator.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page
from config.settings import settings
from tools.metering_results_260901 import ResultRecorder, is_metering_node

from tests.metering_subscription_260901.helpers import (
    CONSOLE_ROOT,
    PORTAL_ROOT,
    RESULTS_DIR,
    cas_login,
)

_recorder: ResultRecorder | None = None
_worker = False
_result_path = RESULTS_DIR / "results.json"


def pytest_addoption(parser):
    parser.addoption("--metering-results", default=None, help="Current-run metering JSON output path")


def pytest_configure(config):
    global _worker, _recorder, _result_path
    from pathlib import Path

    _worker = hasattr(config, "workerinput")
    _recorder = None
    path = config.getoption("--metering-results")
    _result_path = Path(path) if path else RESULTS_DIR / "results.json"


def pytest_collection_modifyitems(config, items):
    for item in items:
        if not is_metering_node(item.nodeid):
            continue
        item.add_marker(pytest.mark.metering_subscription_260901)
        if settings.ENV != "pre":
            item.add_marker(pytest.mark.skip(reason="ENV_MISMATCH: metering260901 only supports PRE"))


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    if is_metering_node(item.nodeid) and settings.ENV != "pre":
        pytest.skip("ENV_MISMATCH: metering260901 only supports PRE")


@pytest.fixture(scope="module")
def wb_page(browser) -> Page:
    """Logged-in workbench page (cloud-pre)."""
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080}, ignore_https_errors=True
    )
    try:
        context.set_default_timeout(15000)
        page = context.new_page()
        cas_login(page, PORTAL_ROOT)
        yield page
    finally:
        context.close()


@pytest.fixture(scope="module")
def cs_page(browser) -> Page:
    """Logged-in console page (irp-pre)."""
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080}, ignore_https_errors=True
    )
    try:
        context.set_default_timeout(15000)
        page = context.new_page()
        cas_login(page, CONSOLE_ROOT)
        yield page
    finally:
        context.close()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if is_metering_node(item.nodeid):
        doc = item.function.__doc__
        report.user_properties.append(("metering_title", doc.strip().splitlines()[0] if doc else item.name))
        scenario = getattr(item, "callspec", None)
        scenario = scenario.params.get("scenario") if scenario else None
        if isinstance(scenario, dict) and "case_ids" in scenario:
            import json
            from core.metering_blackbox_contract import load_manifest

            cases = load_manifest()["cases"]
            titles = {case["case_id"]: case["title"] for case in cases}
            scope_notes = {case["case_id"]: case["scope_note"] for case in cases if case.get("scope_note")}
            report.user_properties.extend([
                ("metering_case_ids", json.dumps(scenario["case_ids"])),
                ("metering_case_titles", json.dumps({cid: titles[cid] for cid in scenario["case_ids"]}, ensure_ascii=False)),
                ("metering_scope_notes", json.dumps(scope_notes, ensure_ascii=False)),
            ])


def pytest_collection_finish(session):
    global _recorder
    if not _worker and not session.config.option.collectonly and any(is_metering_node(item.nodeid) for item in session.items):
        _recorder = ResultRecorder(_result_path, settings.ENV)
        _recorder.flush(-1)


def pytest_runtest_logreport(report):
    global _recorder
    # xdist workers forward reports; only the controller owns the output file.
    if _worker or not is_metering_node(report.nodeid):
        return
    if _recorder is None:
        _recorder = ResultRecorder(_result_path, settings.ENV)
    _recorder.consume(report)
    _recorder.flush(-1)


def pytest_sessionfinish(session, exitstatus):
    if _recorder is not None and not session.config.option.collectonly:
        _recorder.flush(exitstatus)
