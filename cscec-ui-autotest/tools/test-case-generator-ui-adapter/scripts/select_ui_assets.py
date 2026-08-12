#!/usr/bin/env python3
"""Select UI automation asset candidates from generated detailed cases."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

import yaml


ALIASES = {
    "module": ("所属模块", "module"),
    "title": ("标题", "title"),
    "case_type": ("类型", "type", "case_type"),
    "priority": ("优先级", "priority"),
    "precondition": ("前置条件", "precondition", "preconditions"),
    "steps": ("步骤", "steps"),
    "expected": ("预期结果", "expected", "expected_result"),
    "data": ("所涉及到的数据", "data", "test_data"),
}

UI_TYPES = {"功能", "UI", "权限", "回归"}
API_TYPES = {"接口", "性能", "安全", "数据"}

UI_WORDS = (
    "点击",
    "输入",
    "选择",
    "勾选",
    "上传",
    "查看",
    "打开",
    "进入",
    "搜索",
    "筛选",
    "切换",
    "登录",
    "登出",
)
WRITE_WORDS = ("新增", "创建", "保存", "提交", "上传", "编辑", "修改", "变更", "导入", "关联")
DESTRUCTIVE_WORDS = ("删除", "撤回", "审批", "驳回", "终止", "下架", "停用", "作废", "清空")
API_WORDS = ("接口", "API", "数据库", "SQL", "返回码", "入参", "出参", "调用")
MANUAL_WORDS = ("人工确认", "视觉检查", "兼容多浏览器", "多人同时", "并发", "性能", "安全扫描")


def pick(case: dict[str, Any], canonical: str, default: Any = "") -> Any:
    for key in ALIASES[canonical]:
        if key in case and case[key] is not None:
            return case[key]
    return default


def as_text(value: Any) -> str:
    if isinstance(value, list):
        return "\n".join(as_text(item) for item in value)
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def split_types(value: Any) -> set[str]:
    text = as_text(value)
    return {part for part in re.split(r"[/,，、\s]+", text) if part}


def load_cases(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        cases = payload
    elif isinstance(payload, dict) and isinstance(payload.get("cases"), list):
        cases = payload["cases"]
    else:
        raise ValueError("Input must be a case array or an object with a cases array.")

    for index, case in enumerate(cases, 1):
        if not isinstance(case, dict):
            raise ValueError(f"Case {index} is not an object.")
    return cases


def contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word.lower() in text.lower() for word in words)


def module_marker(module: str) -> str:
    mapping = {
        "登录": "login",
        "门户": "login",
        "控制台": "console",
        "服务中心": "console",
        "文档": "doccenter",
        "知识": "doccenter",
        "巡检": "ops",
        "运维": "ops",
    }
    for keyword, marker in mapping.items():
        if keyword in module:
            return marker
    return "module_pending"


def slug(index: int) -> str:
    return f"UI-CAND-{index:04d}"


def classify(case: dict[str, Any], index: int, source_name: str) -> dict[str, Any]:
    module = as_text(pick(case, "module"))
    title = as_text(pick(case, "title")) or f"未命名用例-{index}"
    case_types = split_types(pick(case, "case_type"))
    priority = as_text(pick(case, "priority", "P2")).upper() or "P2"
    precondition = as_text(pick(case, "precondition"))
    steps = as_text(pick(case, "steps"))
    expected = as_text(pick(case, "expected"))
    data = as_text(pick(case, "data"))
    full_text = "\n".join([module, title, " ".join(case_types), precondition, steps, expected, data])

    markers = ["regression", module_marker(module)]
    if contains_any(full_text, DESTRUCTIVE_WORDS):
        risk_marker = "destructive"
    elif contains_any(full_text, WRITE_WORDS):
        risk_marker = "write"
    else:
        risk_marker = "readonly"
    markers.append(risk_marker)

    ui_signal = bool(case_types & UI_TYPES) or contains_any(full_text, UI_WORDS)
    api_signal = bool(case_types & API_TYPES) or contains_any(full_text, API_WORDS)
    manual_signal = contains_any(full_text, MANUAL_WORDS)

    if manual_signal and not ui_signal:
        status = "manual_only"
        reason = "场景依赖人工判断、兼容/性能/安全或多人并发，不适合作为首选 UI 自动化。"
    elif api_signal and not ui_signal:
        status = "api_preferred"
        reason = "主要验证接口、数据或非前端交互，更适合接口/数据校验。"
    elif ui_signal:
        status = "candidate"
        reason = "包含稳定前端交互或功能/UI/权限/回归验证，可进入 UI 自动化候选池。"
    else:
        status = "manual_only"
        reason = "缺少明确前端交互信号，需人工评估后再进入 UI 自动化。"

    prod_eligible = risk_marker == "readonly" and status == "candidate"
    if prod_eligible and priority == "P0":
        markers.insert(0, "smoke")

    return {
        "asset_id": slug(index),
        "source_case": {
            "source_file": source_name,
            "module": module,
            "title": title,
            "type": sorted(case_types),
            "priority": priority,
        },
        "automation": {
            "status": status,
            "suggested_markers": markers,
            "env_policy": {
                "uat": True,
                "pre": True,
                "prod_default": prod_eligible and "smoke" in markers,
                "prod_explicit": prod_eligible,
            },
            "reason": reason,
            "target_test_path": "",
        },
        "promotion": {
            "lifecycle": "new_requirement",
            "uat_evidence": "",
            "pre_evidence": "",
            "prod_regression_since": "",
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Select UI automation candidates from detailed case JSON.")
    parser.add_argument("--input", required=True, help="Path to 详细测试用例数据.json")
    parser.add_argument("--output", required=True, help="YAML output path")
    parser.add_argument("--requirement", default="", help="Requirement or iteration name")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    cases = load_cases(input_path)

    assets = [classify(case, index, input_path.name) for index, case in enumerate(cases, 1)]
    payload = {
        "registry_version": 1,
        "generated_at": date.today().isoformat(),
        "requirement": args.requirement,
        "source": str(input_path),
        "assets": assets,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )

    counts: dict[str, int] = {}
    for asset in assets:
        status = asset["automation"]["status"]
        counts[status] = counts.get(status, 0) + 1
    print(f"Wrote {output_path}")
    print(f"Total cases: {len(assets)}")
    print("Status counts: " + json.dumps(counts, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
