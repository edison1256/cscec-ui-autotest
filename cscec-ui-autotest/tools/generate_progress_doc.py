#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 docs/PROJECT_STATUS.md —— 项目状态文档的单一事实来源。

数据由两个客观来源派生，避免手工维护漂移：
  1. test_assets/registry/ui_case_assets.yaml —— 资产登记表（资产治理状态）
  2. `python run_tests.py --env prod --dry-run` —— 生产默认套件实际收集规模

用法（变更受监控目录后运行一次）：
    python tools/generate_progress_doc.py
"""
from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REGISTRY_PATH = PROJECT_ROOT / "test_assets" / "registry" / "ui_case_assets.yaml"
OUTPUT_PATH = PROJECT_ROOT / "docs" / "PROJECT_STATUS.md"


def load_registry() -> dict:
    with open(REGISTRY_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def collect_prod_stats() -> dict:
    """从 `run_tests.py --env prod --dry-run` 解析生产默认套件规模。"""
    venv_py = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    py = str(venv_py) if venv_py.exists() else sys.executable
    try:
        proc = subprocess.run(
            [py, "run_tests.py", "--env", "prod", "--dry-run"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=180,
        )
        out = proc.stdout + proc.stderr
    except Exception as e:  # 解析失败不应阻断文档生成
        return {"error": str(e)}

    m = re.search(r"(\d+)/(\d+)\s+tests collected\s*\((\d+)\s+deselected\)", out)
    if m:
        return {
            "collected": int(m.group(1)),
            "total": int(m.group(2)),
            "deselected": int(m.group(3)),
        }
    m2 = re.search(r"(\d+)\s+tests collected", out)
    if m2:
        return {"collected": int(m2.group(1)), "total": None, "deselected": None}
    return {"error": "未能解析 dry-run 汇总行", "raw_tail": out[-400:]}


def summarize_assets(registry: dict) -> dict:
    assets = registry.get("assets") or []
    by_lifecycle = Counter(a.get("lifecycle", "unknown") for a in assets)
    by_status = Counter(a.get("automation_status", "unknown") for a in assets)
    by_module = Counter(a.get("module", "unknown") for a in assets)
    unstable = [
        a
        for a in assets
        if a.get("automation_status") == "needs_stabilization"
    ]
    return {
        "total": len(assets),
        "by_lifecycle": by_lifecycle,
        "by_status": by_status,
        "by_module": by_module,
        "unstable": unstable,
    }


def render(registry: dict, stats: dict, summary: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: list[str] = []
    lines.append("# 项目状态文档（自动生成）")
    lines.append("")
    lines.append(f"> 本文件由 `tools/generate_progress_doc.py` 从资产登记表 + 生产 dry-run 自动派生，"
                 f"生成时间 {now}。请勿手工编辑——改完受监控目录后重跑生成器即可。")
    lines.append(">")
    lines.append("> 旧文档 `docs/task-progress-2026-08-12-ui-autotest.md` 已过期被本文件取代。")
    lines.append("")

    # ── Test 套件视角 ──
    lines.append("## 1. 生产默认套件规模（pytest 实际收集）")
    lines.append("")
    if "error" in stats:
        lines.append(f"- ⚠️ dry-run 解析失败：{stats['error']}")
    else:
        total = stats.get("total")
        collected = stats.get("collected")
        deselected = stats.get("deselected")
        if total is not None:
            lines.append(f"- **总用例数**：{total}")
            lines.append(f"- **生产默认收集（smoke + readonly）**：{collected} / {total}")
            lines.append(f"- **被默认排除（write / destructive）**：{deselected}")
        else:
            lines.append(f"- **生产默认收集（smoke + readonly）**：{collected}")
    lines.append("")
    lines.append("> 生产强制走查套件 = `smoke and readonly`，与 AGENTS.md 声明一致，零写入风险。")
    lines.append("")

    # ── 资产治理视角 ──
    lines.append("## 2. 资产治理状态（来自 registry）")
    lines.append("")
    lines.append(f"- **登记资产总数**：{summary['total']}")
    lines.append("")
    lines.append("### 按生命周期（lifecycle）")
    lines.append("")
    lines.append("| lifecycle | 数量 |")
    lines.append("| --- | --- |")
    for k, v in summary["by_lifecycle"].most_common():
        lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("### 按自动化状态（automation_status）")
    lines.append("")
    lines.append("| automation_status | 数量 |")
    lines.append("| --- | --- |")
    for k, v in summary["by_status"].most_common():
        lines.append(f"| {k} | {v} |")
    lines.append("")
    lines.append("### 按模块（module）")
    lines.append("")
    lines.append("| module | 数量 |")
    lines.append("| --- | --- |")
    for k, v in summary["by_module"].most_common():
        lines.append(f"| {k} | {v} |")
    lines.append("")

    # ── 待稳定 / TODO ──
    lines.append("## 3. 待稳定资产与监控项（needs_stabilization）")
    lines.append("")
    unstable = summary["unstable"]
    if not unstable:
        lines.append("- 无。所有登记资产均已稳定。")
    else:
        lines.append(f"共 **{len(unstable)}** 条，根因多为 UAT 未暴露对应菜单入口，处置方式见各条 notes：")
        lines.append("")
        lines.append("| asset_id | module | title | test_path | notes |")
        lines.append("| --- | --- | --- | --- | --- |")
        for a in unstable:
            aid = a.get("asset_id", "")
            mod = a.get("module", "")
            title = a.get("title", "")
            tp = a.get("test_path", "")
            note = (a.get("notes") or "").replace("\n", " ")
            lines.append(f"| {aid} | {mod} | {title} | `{tp}` | {note} |")
    lines.append("")
    lines.append("## 4. 复用与维护约定")
    lines.append("")
    lines.append("- 变更 `pages/ tests/ core/ config/ test_assets/ docs/` 中任一目录后，运行 "
                 "`python tools/generate_progress_doc.py` 刷新本文档。")
    lines.append("- 自动提交前请遵循 AGENTS.md 的 Git 作用域约束（仅暂存本工程 6 个受监控目录）。")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> int:
    if not REGISTRY_PATH.exists():
        print(f"[错误] 找不到资产登记表: {REGISTRY_PATH}", file=sys.stderr)
        return 1
    registry = load_registry()
    stats = collect_prod_stats()
    summary = summarize_assets(registry)
    md = render(registry, stats, summary)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(md, encoding="utf-8")
    print(f"[完成] 状态文档已生成: {OUTPUT_PATH}")
    print(f"  资产总数={summary['total']}  待稳定={len(summary['unstable'])}  "
          f"prod collected={stats.get('collected')}/{stats.get('total')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
