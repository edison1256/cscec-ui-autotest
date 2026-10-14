from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from tools.generate_metering_outline_260901 import annotate, generate, load_results
from tools.metering_results_260901 import ResultRecorder, case_id_from_nodeid

PREFIX = "tests/metering_subscription_260901/test_example.py::"


def report(name="test_m3_1_1__scope", when="call", outcome="passed", reason=""):
    return SimpleNamespace(nodeid=PREFIX + name, when=when, outcome=outcome,
                           longrepr=reason, failed=outcome == "failed", skipped=outcome == "skipped",
                           user_properties=[("metering_title", "Scope")])


@pytest.mark.parametrize("name,expected", [
    ("test_m3_1_1__scope", "M3.1.1"), ("test_f12__removed_user", "F12"),
    ("test_m4_2_1a__query[value]", "M4.2.1"),
])
def test_case_ids(name, expected):
    assert case_id_from_nodeid(PREFIX + name) == expected
    assert case_id_from_nodeid("tests/other/" + name) is None


def test_recorder_does_not_import_stale_results_or_write_on_collection(tmp_path):
    path = tmp_path / "results.json"
    path.write_text('{"results":{"M1.1.1":{"status":"passed"}}}', encoding="utf-8")
    old = path.read_bytes()
    recorder = ResultRecorder(path, "pre")
    assert not recorder.results
    assert path.read_bytes() == old
    recorder.consume(report())
    recorder.flush(0)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert set(data["results"]) == {"M3.1.1"}
    assert data["run_id"] and data["schema_version"] == 2
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("when,outcome,reason,status", [
    ("setup", "passed", "", "not_run"),
    ("setup", "skipped", "ENV_MISMATCH: only PRE", "skipped"),
    ("setup", "failed", "login failed", "failed"),
    ("teardown", "failed", "close failed", "failed"),
])
def test_recorder_covers_setup_and_teardown(tmp_path, when, outcome, reason, status):
    recorder = ResultRecorder(tmp_path / "results.json", "pre")
    if when == "teardown":
        recorder.consume(report())
    recorder.consume(report(when=when, outcome=outcome, reason=reason))
    assert recorder.results["M3.1.1"]["status"] == status


def test_passed_teardown_does_not_hide_call_failure(tmp_path):
    recorder = ResultRecorder(tmp_path / "results.json", "pre")
    recorder.consume(report(outcome="failed", reason="assertion"))
    recorder.consume(report(when="teardown"))
    assert recorder.results["M3.1.1"]["status"] == "failed"


def test_variants_preserve_worst_outcome_and_f12(tmp_path):
    recorder = ResultRecorder(tmp_path / "results.json", "pre")
    recorder.consume(report(name="test_m4_2_1a__query[a]", outcome="failed", reason="bad"))
    recorder.consume(report(name="test_m4_2_1a__query[b]"))
    recorder.consume(report(name="test_f12__removed", when="setup", outcome="skipped", reason="DATA_REQUIRED"))
    assert recorder.results["M4.2.1"]["status"] == "failed"
    assert len(recorder.results["M4.2.1"]["variants"]) == 2
    assert recorder.results["F12"]["classification"] == "DATA_REQUIRED"


def make_outline(path: Path):
    case = {"id": "c1", "title": "Requirement", "style": {"id": "style1"},
            "markers": ["priority-1"], "href": "https://example.org/requirement",
            "notes": {"plain": {"content": "original note"}, "realHTML": {"content": "<b>note</b>"}},
            "children": {"attached": [{"id": "annotation", "title": "Original annotation"}]}}
    sheets = [{"id": "s1", "title": "First", "theme": {"id": "theme1"},
               "relationships": [{"id": "rel1"}],
               "rootTopic": {"id": "r1", "title": "M1.1 Section",
                             "children": {"attached": [case], "detached": [{"id": "floating", "title": "note"}]}}},
              {"id": "s2", "title": "Second", "rootTopic": {"id": "r2", "title": "F12 Requirement"}}]
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("content.json", json.dumps(sheets))
        z.writestr("manifest.json", json.dumps({"file-entries": {"Thumbnails/thumbnail.png": {}, "resources/image.png": {}}}))
        z.writestr("Thumbnails/thumbnail.png", b"old preview")
        z.writestr("resources/image.png", b"original resource")
    return sheets


def test_outline_preserves_source_sheets_metadata_annotations_and_resources(tmp_path):
    source, target = tmp_path / "source.xmind", tmp_path / "out.xmind"
    sheets = make_outline(source)
    original_hash = hashlib.sha256(source.read_bytes()).digest()
    stats = generate(source, target, tmp_path / "missing-results.json")
    assert stats["total"] == stats["not_run"] == 2
    assert stats["passed"] == stats["skipped"] == 0
    assert hashlib.sha256(source.read_bytes()).digest() == original_hash
    with zipfile.ZipFile(target) as z:
        data = json.loads(z.read("content.json"))
        assert len(data) == 2 and data[0]["relationships"] == sheets[0]["relationships"]
        root = data[0]["rootTopic"]
        leaf = root["children"]["attached"][0]
        assert leaf["children"] == sheets[0]["rootTopic"]["children"]["attached"][0]["children"]
        assert leaf["style"] == {"id": "style1"} and leaf["markers"] == ["priority-1"]
        assert root["children"]["detached"][0]["id"] == "floating"
        assert leaf["notes"]["realHTML"]["content"].startswith("<b>note</b>")
        assert "本轮没有" in leaf["notes"]["realHTML"]["content"]
        assert "original note" in leaf["notes"]["plain"]["content"]
        assert z.read("resources/image.png") == b"original resource"
        assert "Thumbnails/thumbnail.png" not in z.namelist()
        assert "Thumbnails/thumbnail.png" not in json.loads(z.read("manifest.json"))["file-entries"]


def test_outline_rejects_source_overwrite_and_legacy_results(tmp_path):
    source = tmp_path / "source.xmind"
    make_outline(source)
    with pytest.raises(ValueError, match="原始大纲"):
        generate(source, source, tmp_path / "missing.json")
    legacy = tmp_path / "legacy.json"
    legacy.write_text('{"results": {}}', encoding="utf-8")
    with pytest.raises(ValueError, match="历史运行"):
        load_results(legacy)


def test_representative_is_not_a_full_regression_pass():
    root, counts, ids = annotate({"title": "M11.1 Shell"}, {
        "M11.1.1": {"status": "passed", "phases": {"call": {"status": "passed"}}},
    })
    assert counts["passed"] == 0 and counts["not_run"] == counts["representative"] == 1
    assert "未执行" in root["title"]
    assert "不等于" in root["notes"]["plain"]["content"]


@pytest.mark.parametrize("classification", ["PENDING_IMPLEMENTATION", "DATA_REQUIRED", "ROLE_REQUIRED"])
def test_skips_are_not_automated_or_passed(classification):
    root, counts, _ = annotate({"title": "F12 Requirement"}, {
        "F12": {"status": "skipped", "classification": classification},
    })
    assert counts["passed"] == 0 and counts["skipped"] == 1
    assert "已执行自动化断言" not in root["title"]
    assert "不可自动化" not in root["title"]


@pytest.mark.parametrize("env", ["uat", "prod"])
def test_environment_guard_runs_before_fixtures(monkeypatch, env):
    from tests.metering_subscription_260901 import conftest as plugin

    monkeypatch.setattr(plugin, "settings", SimpleNamespace(ENV=env))
    item = SimpleNamespace(nodeid=PREFIX + "test_f12__removed", markers=[])
    item.add_marker = item.markers.append
    plugin.pytest_collection_modifyitems(None, [item])
    assert any(mark.name == "skip" for mark in item.markers)
    with pytest.raises(pytest.skip.Exception, match="ENV_MISMATCH"):
        plugin.pytest_runtest_setup(item)


@pytest.mark.parametrize("fixture", ["wb_page", "cs_page"])
def test_login_failure_closes_context(monkeypatch, fixture):
    from tests.metering_subscription_260901 import conftest as plugin

    closed = []
    context = SimpleNamespace(set_default_timeout=lambda _: None, new_page=lambda: object(), close=lambda: closed.append(True))
    browser = SimpleNamespace(new_context=lambda **_: context)

    def fail_login(*_):
        raise RuntimeError("login failed")

    monkeypatch.setattr(plugin, "cas_login", fail_login)
    with pytest.raises(RuntimeError):
        next(getattr(plugin, fixture).__wrapped__(browser))
    assert closed == [True]


def test_worker_never_writes_shared_results(monkeypatch):
    from tests.metering_subscription_260901 import conftest as plugin

    monkeypatch.setattr(plugin, "_worker", True)
    monkeypatch.setattr(plugin, "_recorder", None)
    plugin.pytest_runtest_logreport(report())
    assert plugin._recorder is None


def test_negative_text_assertions_fail_closed():
    from tests.metering_subscription_260901.helpers import visible_texts

    def fail_read(**_):
        raise RuntimeError("page closed")

    page = SimpleNamespace(locator=lambda _: SimpleNamespace(inner_text=fail_read))
    with pytest.raises(RuntimeError, match="page closed"):
        visible_texts(page)


def test_body_text_cannot_substitute_for_table_headers():
    from tests.metering_subscription_260901.helpers import assert_headers_present

    page = SimpleNamespace(locator=lambda _: SimpleNamespace(all=lambda: [], inner_text=lambda **_: "资源名称 服务模式"))
    with pytest.raises(AssertionError, match="缺失表头"):
        assert_headers_present(page, ("资源名称", "服务模式"), "table")


def test_progress_doc_does_not_label_every_deselected_case_as_write():
    from collections import Counter
    from tools.generate_progress_doc import render, summarize_assets

    registry = {"assets": []}
    text = render(registry, {"total": 715, "collected": 115, "deselected": 600},
                  {"total": 113, "classifications": Counter({"mandatory": 44, "conditional": 69})},
                  summarize_assets(registry))
    assert "PRE 专用" in text
    assert "被默认排除（write / destructive）" not in text


def test_progress_collection_preserves_allure_history(monkeypatch):
    from tools import generate_progress_doc as progress

    commands = []

    def fake_run(command, **_):
        commands.append(command)
        return SimpleNamespace(stdout="115/743 tests collected (628 deselected)", stderr="")

    monkeypatch.setattr(progress.subprocess, "run", fake_run)
    assert progress.collect_prod_stats()["collected"] == 115
    assert "--keep-allure-results" in commands[0]


@pytest.mark.parametrize("ready", [False, True])
def test_current_admin_flow_requires_real_subscription_center_render(monkeypatch, ready):
    from tests.metering_subscription_260901 import test_m2_subscription_center as module

    calls = []
    monkeypatch.setattr(module, "open_subscription_center", lambda page: calls.append(page))
    monkeypatch.setattr(module, "wait_list_ready_sc", lambda _: ready)
    monkeypatch.setattr(module, "gateway_error", lambda _: False)
    page = object()
    if ready:
        module._open_sc(page)
    else:
        with pytest.raises(AssertionError, match="未渲染"):
            module._open_sc(page)
    assert calls == [page]
