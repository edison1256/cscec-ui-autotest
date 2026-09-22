"""Regression tests for the BK-CI daily-test wrapper."""

import subprocess

from tools import ci_daily_test


def test_execute_uses_supported_runner_report_arguments(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(ci_daily_test, "ARCHIVE_DIR", tmp_path / "ci")
    monkeypatch.setattr(ci_daily_test, "project_python", lambda: "python")

    def fake_run_capture(cmd, timeout=7200):
        captured["cmd"] = cmd
        return 0, "collected 1 item"

    monkeypatch.setattr(ci_daily_test, "run_capture", fake_run_capture)

    exit_code, collected = ci_daily_test.execute("uat", "smoke", [])

    assert exit_code == 0
    assert collected == 1
    assert "--html-path" in captured["cmd"]
    assert "--allure-dir" in captured["cmd"]
    assert "--html" not in captured["cmd"]
    assert "--self-contained-html" not in captured["cmd"]


def test_execute_wraps_extra_pytest_arguments(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(ci_daily_test, "ARCHIVE_DIR", tmp_path / "ci")
    monkeypatch.setattr(ci_daily_test, "project_python", lambda: "python")

    def fake_run_capture(cmd, timeout=7200):
        captured["cmd"] = cmd
        return 0, "collected 1 item"

    monkeypatch.setattr(ci_daily_test, "run_capture", fake_run_capture)

    ci_daily_test.execute("uat", "smoke", ["--collect-only"])

    index = captured["cmd"].index("--pytest-args")
    assert captured["cmd"][index + 1:] == ["--collect-only"]


def test_clear_stale_contract_summary(tmp_path, monkeypatch):
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    stale_summary = reports_dir / "prod-console-contract-summary.json"
    stale_summary.write_text('{"environment": "prod"}', encoding="utf-8")
    monkeypatch.setattr(ci_daily_test, "REPORTS_DIR", reports_dir)

    ci_daily_test.clear_stale_contract_summary()

    assert not stale_summary.exists()


def test_run_applies_timeout(monkeypatch):
    captured = {}

    def fake_subprocess_run(cmd, **kwargs):
        captured.update(kwargs)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(ci_daily_test.subprocess, "run", fake_subprocess_run)

    assert ci_daily_test.run(["python", "--version"], timeout=17) == 0
    assert captured["timeout"] == 17


def test_parse_collected_prefers_selected_count():
    output = "115/520 tests collected (405 deselected) in 0.30s"

    assert ci_daily_test._parse_collected(output) == 115
