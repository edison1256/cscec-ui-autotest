#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate detailed test-case Markdown from structured JSON data.

Usage:
    py -3 scripts/gen_cases.py --json "详细测试用例数据.json" --output "详细测试用例.md"
    py -3 scripts/gen_cases.py --json "cases.json" --output "cases.md" --title "阶段2：详细测试用例"

Input JSON formats:
    1. {"title": "...", "note": "...", "cases": [{...}, {...}]}
    2. [{...}, {...}]

Each case may use Chinese field names or English aliases:
    所属模块/module, 标题/title, 类型/type, 优先级/priority, 前置条件/precondition,
    负责人/owner, 步骤/steps, 预期结果/expected, 所涉及到的数据/data

steps and expected may be either a string or a list. Lists are rendered as
【1】... with real newlines. Existing "1." numbering is normalized.
"""

import argparse
import json
import re
import sys
from html import escape
from pathlib import Path


HEADERS = [
    "所属模块",
    "标题",
    "类型",
    "优先级",
    "前置条件",
    "负责人",
    "步骤",
    "预期结果",
    "所涉及到的数据",
]

ALIASES = {
    "所属模块": ("所属模块", "module"),
    "标题": ("标题", "title"),
    "类型": ("类型", "type", "case_type"),
    "优先级": ("优先级", "priority"),
    "前置条件": ("前置条件", "precondition", "preconditions"),
    "负责人": ("负责人", "owner", "assignee"),
    "步骤": ("步骤", "steps"),
    "预期结果": ("预期结果", "expected", "expectation", "expected_result"),
    "所涉及到的数据": ("所涉及到的数据", "data", "test_data"),
}

ALLOWED_TYPES = {"功能", "UI", "接口", "异常", "权限", "性能", "兼容", "安全", "数据", "回归"}
ALLOWED_PRIORITIES = {"P0", "P1", "P2"}
DEFAULT_OWNER = "陈方达,周宇康"


class CaseError(ValueError):
    pass


def pick(case, canonical, default=""):
    for key in ALIASES[canonical]:
        if key in case and case[key] is not None:
            return case[key]
    return default


def normalize_newlines(value):
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_numbering(value):
    if isinstance(value, list):
        items = [normalize_newlines(item) for item in value if normalize_newlines(item)]
        return "\n".join(f"【{idx}】{item}" for idx, item in enumerate(items, 1))

    text = normalize_newlines(value)
    if not text:
        return ""

    lines = []
    converted = False
    for line in text.split("\n"):
        match = re.match(r"^\s*(?:【)?(\d+)(?:】|[.)、．])\s*(.*)$", line)
        if match:
            converted = True
            lines.append(f"【{match.group(1)}】{match.group(2).strip()}")
        else:
            lines.append(line.strip())

    if converted:
        return "\n".join(lines).strip()
    if len(lines) == 1 and not lines[0].startswith("【"):
        return f"【1】{lines[0]}"
    return "\n".join(lines).strip()


def normalize_type(value, idx):
    text = normalize_newlines(value)
    if not text:
        raise CaseError(f"case {idx}: 类型不能为空")

    parts = [part for part in re.split(r"[/,，、\s]+", text) if part]
    if len(parts) > 2:
        raise CaseError(f"case {idx}: 类型最多允许 2 个，当前为 {text}")
    invalid = [part for part in parts if part not in ALLOWED_TYPES]
    if invalid:
        raise CaseError(f"case {idx}: 类型非法 {invalid}，允许值为 {sorted(ALLOWED_TYPES)}")
    return "/".join(parts)


def normalize_priority(value, idx):
    text = normalize_newlines(value).upper()
    if text not in ALLOWED_PRIORITIES:
        raise CaseError(f"case {idx}: 优先级非法 {text}，允许值为 P0/P1/P2")
    return text


def normalize_case(raw_case, idx):
    if not isinstance(raw_case, dict):
        raise CaseError(f"case {idx}: 每条用例必须是对象")

    case = {
        "所属模块": normalize_newlines(pick(raw_case, "所属模块")),
        "标题": normalize_newlines(pick(raw_case, "标题")),
        "类型": normalize_type(pick(raw_case, "类型"), idx),
        "优先级": normalize_priority(pick(raw_case, "优先级"), idx),
        "前置条件": normalize_newlines(pick(raw_case, "前置条件", "-")),
        "负责人": normalize_newlines(pick(raw_case, "负责人", DEFAULT_OWNER)) or DEFAULT_OWNER,
        "步骤": normalize_numbering(pick(raw_case, "步骤")),
        "预期结果": normalize_numbering(pick(raw_case, "预期结果")),
        "所涉及到的数据": normalize_newlines(pick(raw_case, "所涉及到的数据", "-")),
    }

    for required in ("所属模块", "标题", "步骤", "预期结果"):
        if not case[required]:
            raise CaseError(f"case {idx}: {required}不能为空")
    return case


def load_cases(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {"title": "阶段2：详细测试用例", "note": "", "cases": data}
    if isinstance(data, dict) and isinstance(data.get("cases"), list):
        return data
    raise CaseError("JSON 顶层必须是用例数组，或包含 cases 数组的对象")


def render_html_table(cases, title, note):
    lines = [f"# {title}", ""]
    if note:
        lines.extend([f"> {note}", ""])
    lines.extend(["<table>", "  <thead>", "    <tr>"])
    for header in HEADERS:
        lines.append(f"      <th>{escape(header)}</th>")
    lines.extend(["    </tr>", "  </thead>", "  <tbody>"])

    for case in cases:
        lines.append("    <tr>")
        for header in HEADERS:
            lines.append(f"      <td>{escape(case[header])}</td>")
        lines.append("    </tr>")

    lines.extend(["  </tbody>", "</table>", ""])
    return "\n".join(lines)


def parse_args():
    parser = argparse.ArgumentParser(description="Generate detailed test-case Markdown from JSON.")
    parser.add_argument("--json", required=True, help="Input JSON case data path")
    parser.add_argument("--output", required=True, help="Output Markdown path")
    parser.add_argument("--title", help="Override document title")
    parser.add_argument("--note", help="Override document note")
    parser.add_argument("--owner", default=DEFAULT_OWNER, help="Default owner when case owner is empty")
    return parser.parse_args()


def main():
    args = parse_args()
    global DEFAULT_OWNER
    DEFAULT_OWNER = args.owner

    payload = load_cases(args.json)
    title = args.title or payload.get("title") or "阶段2：详细测试用例"
    note = args.note if args.note is not None else payload.get("note", "")
    cases = [normalize_case(case, idx) for idx, case in enumerate(payload["cases"], 1)]

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_html_table(cases, title, note), encoding="utf-8")

    print(f"Markdown文件已生成: {output}")
    print(f"总用例数: {len(cases)}")


if __name__ == "__main__":
    try:
        main()
    except CaseError as exc:
        print(f"错误: {exc}", file=sys.stderr)
        sys.exit(1)
