"""Local fixtures for metering_subscription_260901 PRE coverage.

Provides module-scoped logged-in pages for both split domains plus a
session-wide case-result recorder consumed by the outline generator.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page
from config.settings import settings
from tools.metering_results_260901 import ResultRecorder, case_id_from_nodeid

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
        if case_id_from_nodeid(item.nodeid) is None:
            continue
        item.add_marker(pytest.mark.metering_subscription_260901)
        if settings.ENV != "pre":
            item.add_marker(pytest.mark.skip(reason="ENV_MISMATCH: metering260901 only supports PRE"))


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    if case_id_from_nodeid(item.nodeid) and settings.ENV != "pre":
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
    if case_id_from_nodeid(item.nodeid):
        doc = item.function.__doc__
        report.user_properties.append(("metering_title", doc.strip().splitlines()[0] if doc else item.name))


def pytest_runtest_logreport(report):
    global _recorder
    # xdist workers forward reports; only the controller owns the output file.
    if _worker or case_id_from_nodeid(report.nodeid) is None:
        return
    if _recorder is None:
        _recorder = ResultRecorder(_result_path, settings.ENV)
    _recorder.consume(report)


def pytest_sessionfinish(session, exitstatus):
    if _recorder is not None and not session.config.option.collectonly:
        _recorder.flush(exitstatus)
