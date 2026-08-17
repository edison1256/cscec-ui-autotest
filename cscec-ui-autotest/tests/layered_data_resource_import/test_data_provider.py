from __future__ import annotations

from pathlib import Path

from tests.layered_data_resource_import import data_provider


def test_get_dataset_file_path_prefers_project_file_by_default_for_uat(tmp_path: Path, monkeypatch):
    project_root = tmp_path / "datasets"
    layered_dir = project_root / "layered_import"
    desktop_dir = tmp_path / "desktop"
    layered_dir.mkdir(parents=True)
    desktop_dir.mkdir()
    project_file = layered_dir / "normalized.xlsx"
    desktop_file = desktop_dir / "原始文件.xlsx"
    project_file.write_text("project", encoding="utf-8")
    desktop_file.write_text("desktop", encoding="utf-8")

    monkeypatch.setattr(data_provider, "BASE_DATASET_DIR", project_root)
    monkeypatch.setattr(data_provider, "DESKTOP_DATASET_DIR", desktop_dir)
    monkeypatch.setenv("ENV", "uat")
    monkeypatch.delenv("UI_IMPORT_USE_DESKTOP_DATASETS", raising=False)

    assert data_provider.get_dataset_file_path("normalized.xlsx", "原始文件.xlsx") == project_file


def test_get_dataset_file_path_uses_desktop_original_file_when_explicitly_enabled(tmp_path: Path, monkeypatch):
    project_root = tmp_path / "datasets"
    layered_dir = project_root / "layered_import"
    desktop_dir = tmp_path / "desktop"
    layered_dir.mkdir(parents=True)
    desktop_dir.mkdir()
    project_file = layered_dir / "normalized.xlsx"
    desktop_file = desktop_dir / "原始文件.xlsx"
    project_file.write_text("project", encoding="utf-8")
    desktop_file.write_text("desktop", encoding="utf-8")

    monkeypatch.setattr(data_provider, "BASE_DATASET_DIR", project_root)
    monkeypatch.setattr(data_provider, "DESKTOP_DATASET_DIR", desktop_dir)
    monkeypatch.setenv("ENV", "uat")
    monkeypatch.setenv("UI_IMPORT_USE_DESKTOP_DATASETS", "true")

    assert data_provider.get_dataset_file_path("normalized.xlsx", "原始文件.xlsx") == desktop_file


def test_get_dataset_file_path_prefers_pre_dataset_for_pre(tmp_path: Path, monkeypatch):
    project_root = tmp_path / "datasets"
    pre_dir = project_root / "pre"
    desktop_dir = tmp_path / "desktop"
    pre_dir.mkdir(parents=True)
    desktop_dir.mkdir()
    pre_file = pre_dir / "normalized.xlsx"
    desktop_file = desktop_dir / "原始文件.xlsx"
    pre_file.write_text("pre", encoding="utf-8")
    desktop_file.write_text("desktop", encoding="utf-8")

    monkeypatch.setattr(data_provider, "BASE_DATASET_DIR", project_root)
    monkeypatch.setattr(data_provider, "DESKTOP_DATASET_DIR", desktop_dir)
    monkeypatch.setenv("ENV", "pre")

    assert data_provider.get_dataset_file_path("normalized.xlsx", "原始文件.xlsx") == pre_file


def test_import_run_id_is_ascii_and_environment_scoped(monkeypatch):
    monkeypatch.setenv("ENV", "pre")

    run_id = data_provider.import_run_id("m03")

    assert run_id.startswith("m03_pre_")
    assert run_id.isascii()
    assert " " not in run_id
