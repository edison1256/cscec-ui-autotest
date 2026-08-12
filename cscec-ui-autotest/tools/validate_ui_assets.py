#!/usr/bin/env python3
"""Validate the UI automation asset registry."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml


REQUIRED_ASSET_FIELDS = {
    "asset_id",
    "module",
    "title",
    "lifecycle",
    "automation_status",
    "markers",
    "env_policy",
}

LIFECYCLES = {
    "new_requirement",
    "candidate",
    "uat_automated",
    "pre_verified",
    "prod_regression",
    "manual_only",
    "api_preferred",
    "deprecated",
}

STATUSES = {
    "candidate",
    "automated",
    "needs_stabilization",
    "manual_only",
    "api_preferred",
    "deprecated",
}

ENV_FIELDS = {"uat", "pre", "prod_default", "prod_explicit"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate UI case asset registry YAML.")
    parser.add_argument(
        "--registry",
        default="test_assets/registry/ui_case_assets.yaml",
        help="Registry YAML path",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = Path(args.registry)
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    errors: list[str] = []

    if not isinstance(payload, dict):
        errors.append("registry root must be an object")
    else:
        assets = payload.get("assets")
        if not isinstance(assets, list):
            errors.append("assets must be a list")
            assets = []

        seen_ids = set()
        for index, asset in enumerate(assets, 1):
            if not isinstance(asset, dict):
                errors.append(f"asset {index}: must be an object")
                continue

            missing = sorted(REQUIRED_ASSET_FIELDS - set(asset))
            if missing:
                errors.append(f"asset {index}: missing fields {missing}")

            asset_id = asset.get("asset_id")
            if asset_id in seen_ids:
                errors.append(f"asset {index}: duplicate asset_id {asset_id}")
            seen_ids.add(asset_id)

            lifecycle = asset.get("lifecycle")
            if lifecycle not in LIFECYCLES:
                errors.append(f"{asset_id}: invalid lifecycle {lifecycle}")

            status = asset.get("automation_status")
            if status not in STATUSES:
                errors.append(f"{asset_id}: invalid automation_status {status}")

            markers = asset.get("markers")
            if not isinstance(markers, list) or not markers:
                errors.append(f"{asset_id}: markers must be a non-empty list")

            env_policy = asset.get("env_policy")
            if not isinstance(env_policy, dict):
                errors.append(f"{asset_id}: env_policy must be an object")
            else:
                missing_env = sorted(ENV_FIELDS - set(env_policy))
                if missing_env:
                    errors.append(f"{asset_id}: env_policy missing {missing_env}")
                for key in ENV_FIELDS & set(env_policy):
                    if not isinstance(env_policy[key], bool):
                        errors.append(f"{asset_id}: env_policy.{key} must be boolean")

            if lifecycle == "prod_regression" and "readonly" not in (markers or []):
                errors.append(f"{asset_id}: prod_regression assets must include readonly")

            if env_policy and env_policy.get("prod_default"):
                marker_set = set(markers or [])
                if not {"smoke", "readonly"}.issubset(marker_set):
                    errors.append(f"{asset_id}: prod_default requires smoke + readonly")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"Registry valid: {path}")
    print(f"Assets: {len(payload.get('assets', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
