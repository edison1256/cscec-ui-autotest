"""Local fixtures for metering_subscription_260901 PRE coverage.

Provides module-scoped logged-in pages for both split domains plus a
session-wide case-result recorder consumed by the outline generator.
"""

from __future__ import annotations

import json
import re
from datetime import datetime

import pytest
from playwright.sync_api import Page

from tests.metering_subscription_260901.helpers import (
    CONSOLE_ROOT,
    PORTAL_ROOT,
    RESULTS_DIR,
    cas_login,
)

_CASE_ID_PAT = re.compile(r"m(\d{1,2})_(\d{1,2})_(\d{1,2})[a-z]?__")
SKIP_CLASS_PAT = re.compile(
    r"(ENTRY_MISSING|ROLE_REQUIRED|DATA_REQUIRED|NOT_AUTOMATABLE|ENV_LIMITED)"
)


class ResultRecorder:
    """Collect per-case outcomes into reports/metering260901/results.json."""

    def __init__(self) -> None:
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        self.path = RESULTS_DIR / "results.json"
        self.results: dict[str, dict] = {}
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self.results = data.get("results", {}) if isinstance(data, dict) else {}
            except Exception:
                self.results = {}

    def add(self, case_id: str, payload: dict) -> None:
        self.results[case_id] = payload
        self._flush()

    def _flush(self) -> None:
        self.path.write_text(
            json.dumps(
                {
                    "generated_at": datetime.now().isoformat(timespec="seconds"),
                    "env": settings_env(),
                    "results": self.results,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def settings_env() -> str:
    from config.settings import settings

    return settings.ENV


_recorder = ResultRecorder()


@pytest.fixture(scope="session")
def metering_recorder() -> ResultRecorder:
    return _recorder


@pytest.fixture(scope="module")
def wb_page(browser) -> Page:
    """Logged-in workbench page (cloud-pre)."""
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080}, ignore_https_errors=True
    )
    context.set_default_timeout(15000)
    page = context.new_page()
    cas_login(page, PORTAL_ROOT)
    yield page
    context.close()


@pytest.fixture(scope="module")
def cs_page(browser) -> Page:
    """Logged-in console page (irp-pre)."""
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080}, ignore_https_errors=True
    )
    context.set_default_timeout(15000)
    page = context.new_page()
    cas_login(page, CONSOLE_ROOT)
    yield page
    context.close()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if rep.when != "call":
        return
    match = _CASE_ID_PAT.search(item.name)
    if not match:
        return
    case_id = f"M{match.group(1)}.{match.group(2)}.{match.group(3)}"
    entry = {
        "title": item.function.__doc__.strip().splitlines()[0] if item.function.__doc__ else item.name,
        "status": rep.outcome,
        "nodeid": item.nodeid,
    }
    if rep.outcome == "failed":
        entry["error"] = str(rep.longrepr)[:1200]
    if rep.outcome == "skipped":
        reason = str(rep.longrepr)
        match_skip = SKIP_CLASS_PAT.search(reason)
        entry["skip_reason"] = reason[-500:]
        entry["classification"] = match_skip.group(1) if match_skip else "SKIPPED"
    _recorder.add(case_id, entry)
