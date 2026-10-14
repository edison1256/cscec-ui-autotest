"""Generate a separate annotated XMind without altering the source structure."""

from __future__ import annotations

import argparse
import copy
import html
import json
import os
import re
import shutil
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS = PROJECT_ROOT / "reports/metering260901/results.json"
ID_TOKEN = re.compile(r"^([MF]\d{1,2}(?:\.\d{1,2})*)\b")
SHELLS = {"M11.1": "M11.1.1", "M11.2": "M11.2.1", "M11.3": "M11.3.1"}
CLASS_LABEL = {
    "CONTRACT_DIFFERENCE": "需求契约待复核",
    "ENTRY_MISSING": "需求差异待复核",
    "ROLE_REQUIRED": "待角色/手工协同",
    "DATA_REQUIRED": "待数据/流程",
    "PENDING_IMPLEMENTATION": "可自动化待实现",
    "OUT_OF_SCOPE": "本轮范围外",
    "NOT_AUTOMATABLE": "专项/手工协同",
    "ENV_LIMITED": "环境受限待复核",
    "ENV_MISMATCH": "环境不匹配",
}
STATUS_LABEL = {"passed": "通过", "failed": "失败", "skipped": "跳过", "not_run": "未执行"}


def load_results(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != 2 or not data.get("run_id"):
        raise ValueError("旧结果可能混入历史运行，请重新执行套件后再生成大纲")
    if not isinstance(data.get("results"), dict):
        raise ValueError("结果文件缺少 results 对象")
    return data


def append_note(node: dict, text: str) -> None:
    notes = node.setdefault("notes", {})
    plain = notes.setdefault("plain", {})
    existing = plain.get("content", "")
    plain["content"] = (existing + "\n" + text).strip()
    rich = notes.get("realHTML")
    if isinstance(rich, dict) and isinstance(rich.get("content"), str):
        rich["content"] += "<p>" + html.escape(text).replace("\n", "<br/>") + "</p>"


def annotate(root: dict, results: dict) -> tuple[dict, Counter, set[str]]:
    """Keep topic metadata and annotation children; count only coverage topics."""
    result = copy.deepcopy(root)
    counts: Counter = Counter()
    ids: set[str] = set()

    def case(node: dict, case_id: str) -> None:
        if case_id in ids:
            raise ValueError(f"大纲编号重复: {case_id}")
        ids.add(case_id)
        record = results.get(case_id)
        status = record.get("status", "not_run") if record else "not_run"
        if status not in STATUS_LABEL:
            raise ValueError(f"不支持的执行状态: {status}")
        counts["total"] += 1
        counts[status] += 1
        classification = record.get("classification") if record else None
        label = CLASS_LABEL.get(classification, STATUS_LABEL[status])
        scope_note = record.get("scope_note") if record else None
        if scope_note and status == "passed":
            label = "限定范围通过"
            counts["limited_scope"] += 1
        # Setup/auth failures and skips do not prove an automated assertion exists.
        phases = record.get("phases", {}) if record else {}
        implemented = phases.get("call", {}).get("status") in {"passed", "failed"}
        auto = "已执行自动化断言" if implemented else "待执行/待补齐"
        node["title"] = f"[{case_id}][{auto}][{label}] {node.get('title', '')}"
        notes = ["执行说明：" + label]
        if record:
            if scope_note:
                notes.append("覆盖边界：" + scope_note)
            reason = record.get("error") or record.get("skip_reason") or ""
            if reason:
                notes.append("结果摘要：" + str(reason)[:1200])
            notes.append("测试定位：" + record.get("nodeid", ""))
        else:
            notes.append("本轮没有该项执行结果，不视为通过。")
        representative = results.get(SHELLS.get(case_id))
        if representative:
            notes.append(
                f"代表面 {SHELLS[case_id]}："
                f"{STATUS_LABEL.get(representative.get('status'), '未执行')}；"
                "仅代表性检查，不等于该小节全量回归通过。"
            )
            counts["representative"] += 1
        append_note(node, "\n".join(notes))

    def visit(node: dict, prefix: str | None = None) -> None:
        title = node.get("title", "").strip()
        own = ID_TOKEN.match(title)
        children = node.get("children", {}).get("attached", [])
        if own and not children:
            case(node, own.group(1))
            return
        if own:
            prefix = own.group(1)
        index = 0
        for child in children:
            if ID_TOKEN.match(child.get("title", "").strip()):
                visit(child, prefix)
            else:
                index += 1
                case(child, f"{prefix}.{index}" if prefix else f"RAW.{index}")
                # Its children are original case annotations, not extra cases.

    visit(result)
    return result, counts, ids


def generate(source: Path, target: Path, result_path: Path) -> dict:
    source, target = source.resolve(), target.resolve()
    result_path = result_path.resolve()
    if source == target or (target.exists() and os.path.samefile(source, target)):
        raise ValueError("输出文件不能是原始大纲")
    if target == result_path or (target.exists() and result_path.exists()
                                 and os.path.samefile(target, result_path)):
        raise ValueError("输出文件不能覆盖结果文件")
    data = load_results(result_path)
    results = data.get("results", {})
    counts: Counter = Counter()
    ids: set[str] = set()
    with zipfile.ZipFile(source) as archive:
        sheets = json.loads(archive.read("content.json").decode("utf-8"))
        for sheet in sheets:
            root, stats, sheet_ids = annotate(sheet["rootTopic"], results)
            if ids & sheet_ids:
                raise ValueError("不同工作表存在重复用例编号")
            counts.update(stats)
            ids.update(sheet_ids)
            summary = (
                f"本轮结果：环境 {data.get('env', '未执行')}；"
                f"运行 {data.get('run_id', '无')}；"
                f"结果时间 {data.get('generated_at', '无')}；"
                f"退出码 {data.get('exitstatus', '无')}。"
                f"大纲覆盖项 {stats['total']}，通过 {stats['passed']}，"
                f"失败 {stats['failed']}，跳过 {stats['skipped']}，"
                f"通过项中限定范围 {stats['limited_scope']}，"
                f"未执行 {stats['not_run']}。收集/跳过不等于自动化覆盖。"
                "本文件独立生成，保留原批注及资源；原始大纲未修改。"
            )
            append_note(root, summary)
            sheet["rootTopic"] = root

        entries = {info.filename: (info, archive.read(info)) for info in archive.infolist()}
    entries["content.json"] = (
        entries["content.json"][0],
        json.dumps(sheets, ensure_ascii=False, indent=1).encode("utf-8"),
    )
    thumbnails = {name for name in entries if name.startswith("Thumbnails/")}
    for name in thumbnails:
        del entries[name]
    if "manifest.json" in entries:
        info, blob = entries["manifest.json"]
        manifest = json.loads(blob.decode("utf-8"))
        for name in thumbnails:
            manifest.get("file-entries", {}).pop(name, None)
        entries["manifest.json"] = (info, json.dumps(manifest, ensure_ascii=False).encode("utf-8"))
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        backup = target.with_suffix(target.suffix + ".bak")
        if backup == source or (backup.exists() and os.path.samefile(source, backup)):
            raise ValueError("备份路径不能覆盖原始大纲")
        shutil.copy2(target, backup)
    fd, temp_name = tempfile.mkstemp(prefix=".metering-", suffix=".xmind", dir=target.parent)
    os.close(fd)
    temporary = Path(temp_name)
    try:
        with zipfile.ZipFile(temporary, "w") as output:
            for info, blob in entries.values():
                output.writestr(info, blob)
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        **{key: counts[key] for key in ("total", "passed", "failed", "skipped", "not_run", "representative")},
        "unmatched": sorted(set(results) - ids - set(SHELLS.values())),
        "output": str(target),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="原始 XMind（只读）")
    parser.add_argument("--output", type=Path, required=True, help="独立生成的 XMind")
    parser.add_argument("--results", type=Path, default=RESULTS)
    args = parser.parse_args()
    try:
        summary = generate(args.source, args.output, args.results)
    except (ValueError, OSError, zipfile.BadZipFile) as exc:
        parser.exit(1, f"生成失败: {exc}\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
