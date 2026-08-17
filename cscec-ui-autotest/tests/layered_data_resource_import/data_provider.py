"""
Data-driven provider for Layered Data Resource Import tests.
Loads datasets and test parameters dynamically based on current environment (UAT vs PRE).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from uuid import uuid4
import yaml

from config.settings import settings

BASE_DATASET_DIR = Path(__file__).resolve().parent.parent.parent / "test_assets" / "datasets"
DESKTOP_DATASET_DIR = Path(r"C:\Users\CFD\Desktop\260812")


def get_current_dataset_dir() -> Path:
    """Return dataset directory for current environment."""
    env = (os.getenv("ENV") or settings.ENV or "uat").lower()
    if env == "pre":
        pre_dir = BASE_DATASET_DIR / "pre"
        if pre_dir.exists():
            return pre_dir
    return BASE_DATASET_DIR / "layered_import"


def import_run_id(prefix: str = "import") -> str:
    """Return a short environment-scoped token for repeatable write tests."""
    env = (os.getenv("ENV") or settings.ENV or "uat").lower()
    safe_prefix = re.sub(r"[^A-Za-z0-9_]+", "_", prefix).strip("_").lower() or "import"
    return f"{safe_prefix}_{env}_{uuid4().hex[:10]}"


def _use_desktop_datasets() -> bool:
    return (os.getenv("UI_IMPORT_USE_DESKTOP_DATASETS") or "").lower() in {"1", "true", "yes"}


def load_manifest() -> dict[str, Any]:
    """Load the dataset manifest YAML for current environment."""
    manifest_path = get_current_dataset_dir() / "manifest.yaml"
    if not manifest_path.exists():
        manifest_path = BASE_DATASET_DIR / "layered_import" / "manifest.yaml"
    if not manifest_path.exists():
        return {}
    with manifest_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def get_dataset_file_path(filename: str, original_filename: str | None = None) -> Path:
    """Resolve file path within current environment datasets."""
    env = (os.getenv("ENV") or settings.ENV or "uat").lower()
    if env != "pre" and _use_desktop_datasets():
        for desktop_name in [original_filename, filename]:
            if desktop_name:
                desktop_path = DESKTOP_DATASET_DIR / desktop_name
                if desktop_path.exists():
                    return desktop_path

    dataset_dir = get_current_dataset_dir()
    project_path = dataset_dir / filename
    if project_path.exists():
        return project_path

    # Fallback to UAT dataset folder
    uat_path = BASE_DATASET_DIR / "layered_import" / filename
    if uat_path.exists():
        return uat_path

    if _use_desktop_datasets():
        for desktop_name in [original_filename, filename]:
            if desktop_name:
                desktop_path = DESKTOP_DATASET_DIR / desktop_name
                if desktop_path.exists():
                    return desktop_path

    return project_path


def get_m02_dataset(key: str) -> dict[str, Any]:
    """Retrieve M02 dataset entry by key."""
    manifest = load_manifest()
    datasets = manifest.get("m02_datasets", {})
    if key not in datasets:
        # Fallback to UAT manifest
        uat_manifest_path = BASE_DATASET_DIR / "layered_import" / "manifest.yaml"
        if uat_manifest_path.exists():
            with uat_manifest_path.open(encoding="utf-8") as f:
                uat_manifest = yaml.safe_load(f) or {}
                datasets = uat_manifest.get("m02_datasets", {})
    if key not in datasets:
        raise KeyError(f"M02 dataset '{key}' not found for env '{settings.ENV}'")
    entry = dict(datasets[key])
    entry["file_path"] = get_dataset_file_path(entry["filename"], entry.get("original_filename"))
    return entry


def get_m03_dataset(key: str) -> dict[str, Any]:
    """Retrieve M03 dataset entry by key."""
    manifest = load_manifest()
    datasets = manifest.get("m03_datasets", {})
    if key not in datasets:
        uat_manifest_path = BASE_DATASET_DIR / "layered_import" / "manifest.yaml"
        if uat_manifest_path.exists():
            with uat_manifest_path.open(encoding="utf-8") as f:
                uat_manifest = yaml.safe_load(f) or {}
                datasets = uat_manifest.get("m03_datasets", {})
    if key not in datasets:
        raise KeyError(f"M03 dataset '{key}' not found for env '{settings.ENV}'")
    entry = dict(datasets[key])
    entry["file_path"] = get_dataset_file_path(entry["filename"], entry.get("original_filename"))
    return entry
