"""对比 UAT / PRE / PROD 三套环境的用例覆盖，找出可互补的缺口。

数据源：`test_assets/registry/ui_case_assets.yaml` 里每条资产的 `env_policy`。

判定口径：
  - 「仅 UAT」= uat:true 且 pre:false —— PRE 上没有对应覆盖
  - 「仅 PRE」= pre:true 且 uat:false —— UAT 上没有对应覆盖
  - 「双环境」= 两者都 true（**仅代表声明，不代表实际能跑通**）

注意（2026-11-18 实测教训）：
  env_policy 只说明"登记时认为适用"，与"当前环境实际能否跑通"是两件事。
  抽样验证发现 tests/console/test_resource_baseline.py 在 UAT 上也大面积失败
  （1 passed / 3 failed），说明这属于**用例债**，不是环境差异。
  因此本工具只做覆盖面盘点，真实可跑性必须靠 --probe 实测。

用法：
    python tools/compare_env_coverage.py
    python tools/compare_env_coverage.py --markdown   # 输出 Markdown 表
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

import yaml

PROJECT = Path(__file__).resolve().parent.parent
REGISTRY = PROJECT / "test_assets/registry/ui_case_assets.yaml"


def load_assets() -> list[dict]:
    data = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    return data.get("assets") or []


def env_of(asset: dict) -> str:
    p = asset.get("env_policy") or {}
    uat, pre = bool(p.get("uat")), bool(p.get("pre"))
    prod = bool(p.get("prod_default")) or bool(p.get("prod_explicit"))
    if uat and pre:
        return "both"
    if uat:
        return "only_uat"
    if pre:
        return "only_pre"
    if prod:
        return "only_prod"
    return "none"


def main() -> int:
    markdown = "--markdown" in sys.argv
    assets = load_assets()

    by_module: dict[str, defaultdict[str, int]] = defaultdict(lambda: defaultdict(int))
    groups: dict[str, list[dict]] = defaultdict(list)
    for a in assets:
        env = env_of(a)
        by_module[a.get("module", "?")][env] += 1
        by_module[a.get("module", "?")]["total"] += 1
        groups[env].append(a)

    if markdown:
        print("| 模块 | 双环境 | 仅UAT | 仅PRE | 仅PROD | 合计 |")
        print("| --- | --- | --- | --- | --- | --- |")
        for m, c in sorted(by_module.items(), key=lambda kv: -kv[1]["total"]):
            print(
                f"| {m} | {c['both']} | {c['only_uat']} | {c['only_pre']} "
                f"| {c['only_prod']} | {c['total']} |"
            )
    else:
        print(f"资产总数 {len(assets)}\n")
        print(f"{'模块':<26}{'双环境':>7}{'仅UAT':>7}{'仅PRE':>7}{'仅PROD':>8}{'合计':>7}")
        print("-" * 62)
        for m, c in sorted(by_module.items(), key=lambda kv: -kv[1]["total"]):
            print(
                f"{m[:24]:<26}{c['both']:>7}{c['only_uat']:>7}{c['only_pre']:>7}"
                f"{c['only_prod']:>8}{c['total']:>7}"
            )
        print("-" * 62)
        print(
            f"{'合计':<26}{len(groups['both']):>7}{len(groups['only_uat']):>7}"
            f"{len(groups['only_pre']):>7}{len(groups['only_prod']):>8}{len(assets):>7}"
        )

    for key, label in (("only_uat", "仅 UAT（PRE 无覆盖）"), ("only_pre", "仅 PRE（UAT 无覆盖）")):
        items = groups.get(key) or []
        print(f"\n=== {label}：{len(items)} 条 ===")
        for a in items:
            print(f"  {a['asset_id']:26} {(a.get('title') or '')[:44]}")
            tp = a.get("test_path") or ""
            if tp:
                print(f"    path: {tp[:96]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
