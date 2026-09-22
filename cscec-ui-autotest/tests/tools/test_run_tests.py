"""Unit tests for runner artifact maintenance."""

from pathlib import Path
import sys

import pytest

import run_tests


def test_prepare_allure_results_replaces_stale_results(tmp_path, monkeypatch):
    monkeypatch.setattr(run_tests, "PROJECT_DIR", tmp_path)
    results_dir = tmp_path / "reports" / "allure-results"
    results_dir.mkdir(parents=True)
    stale_result = results_dir / "stale.json"
    stale_result.write_text("{}", encoding="utf-8")

    run_tests._prepare_allure_results(keep_existing=False)

    assert results_dir.is_dir()
    assert not stale_result.exists()


def test_prepare_allure_results_can_keep_history(tmp_path, monkeypatch):
    monkeypatch.setattr(run_tests, "PROJECT_DIR", tmp_path)
    results_dir = tmp_path / "reports" / "allure-results"
    results_dir.mkdir(parents=True)
    existing_result = results_dir / "existing.json"
    existing_result.write_text("{}", encoding="utf-8")

    run_tests._prepare_allure_results(keep_existing=True)

    assert existing_result == Path(results_dir / "existing.json")
    assert existing_result.exists()


def test_report_paths_are_translated_to_supported_pytest_arguments(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(run_tests, "PROJECT_DIR", tmp_path)
    monkeypatch.setattr(run_tests, "_load_env_file", lambda: None)
    monkeypatch.setattr(run_tests, "_project_python", lambda: "python")
    monkeypatch.setattr(
        run_tests,
        "_run",
        lambda cmd: captured.setdefault("cmd", cmd) and 0,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_tests.py",
            "--env",
            "uat",
            "--dry-run",
            "--html-path",
            "reports/ci/report.html",
            "--allure-dir",
            "reports/ci/allure-results",
            "--pytest-args",
            "-k",
            "ticket",
        ],
    )

    with pytest.raises(SystemExit) as exc_info:
        run_tests.main()

    assert exc_info.value.code == 0
    assert captured["cmd"][-7:] == [
        "--html",
        "reports/ci/report.html",
        "--self-contained-html",
        "--alluredir=reports/ci/allure-results",
        "--collect-only",
        "-k",
        "ticket",
    ]
