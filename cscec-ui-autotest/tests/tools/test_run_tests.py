"""Unit tests for runner artifact maintenance."""

from pathlib import Path

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
