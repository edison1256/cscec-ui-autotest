"""
Data-driven provider for Layered Data Resource Import tests.
Loads datasets and test parameters directly from project asset repository.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import yaml

DATASET_DIR = Path(__file__).resolve().parent.parent.parent / "test_assets" / "datasets" / "layered_import"
FALLBACK_DESKTOP_DIR = Path(r"C:\Users\CFD\Desktop\260812")
MANIFEST_PATH = DATASET_DIR / "manifest.yaml"


def load_manifest() -> dict[str, Any]:
    """Load the dataset manifest YAML."""
    if not MANIFEST_PATH.exists():
        return {}
    with MANIFEST_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


_MANIFEST = load_manifest()


def get_dataset_file_path(filename: str) -> Path:
    """Resolve file path within project datasets first, fallback to desktop."""
    project_path = DATASET_DIR / filename
    if project_path.exists():
        return project_path

    desktop_path = FALLBACK_DESKTOP_DIR / filename
    if desktop_path.exists():
        return desktop_path

    # Check if filename is an alias
    return project_path


def get_m02_dataset(key: str) -> dict[str, Any]:
    """Retrieve M02 dataset entry by key."""
    datasets = _MANIFEST.get("m02_datasets", {})
    if key not in datasets:
        raise KeyError(f"M02 dataset '{key}' not found in {MANIFEST_PATH}")
    entry = dict(datasets[key])
    entry["file_path"] = get_dataset_file_path(entry["filename"])
    return entry


def get_m03_dataset(key: str) -> dict[str, Any]:
    """Retrieve M03 dataset entry by key."""
    datasets = _MANIFEST.get("m03_datasets", {})
    if key not in datasets:
        raise KeyError(f"M03 dataset '{key}' not found in {MANIFEST_PATH}")
    entry = dict(datasets[key])
    entry["file_path"] = get_dataset_file_path(entry["filename"])
    return entry


def get_all_m02_error_datasets() -> list[tuple[str, str, list[str]]]:
    """Return parameterized list of (test_id, filename, expected_snippets)."""
    m02_data = _MANIFEST.get("m02_datasets", {})
    cases = []
    for key, data in m02_data.items():
        if data.get("expected_status") == "error":
            cases.append((key, data["filename"], data.get("expected_error_snippets", ["错误"])))
    return cases


def get_all_m02_duplicate_datasets() -> list[tuple[str, str, str]]:
    """Return parameterized list of (test_id, filename, description)."""
    m02_data = _MANIFEST.get("m02_datasets", {})
    cases = []
    for key, data in m02_data.items():
        if data.get("has_conflict"):
            cases.append((key, data["filename"], data.get("description", "")))
    return cases
