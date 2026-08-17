from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_validate_ui_assets_rejects_missing_automated_test_path(tmp_path: Path):
    registry = tmp_path / "ui_case_assets.yaml"
    registry.write_text(
        """
registry_version: 1
updated_at: "2026-08-17"
assets:
  - asset_id: UI-BAD-001
    module: bad
    title: bad automated path
    lifecycle: uat_automated
    automation_status: automated
    test_path: tests/no_such_module.py::TestMissing::test_missing
    markers:
      - regression
    env_policy:
      uat: true
      pre: true
      prod_default: false
      prod_explicit: false
""".strip(),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, "tools/validate_ui_assets.py", "--registry", str(registry)],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 1
    assert "test_path" in result.stderr
