"""Generate the automation outline xmind for metering-subscription 260901.

Numbering: use the outline's own (nominal) numbers.
- Module/section titles carry M<module>[.<section>] prefixes.
- Leaf case id = <section prefix>.<case index>; short annotation leaves
  (no colon, no 期望, <=12 chars) attach to the previous case as notes and
  do NOT consume a case index.
- Top-level leaves like "F12 ..." use their own token as case id.
- Bare leaves that already start with M<..> (e.g. empty-shell sections
  "M11.1 ...") use that token as case id.
"""

from __future__ import annotations

import json
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

MASTER = Path(r"D:/Doc/一体化/用例/计量订阅260901测试大纲.xmind")
TARGET = Path(r"D:/Doc/一体化/用例/计量订阅260901自动化测试大纲.xmind")
RESULTS = Path(
    r"D:/Automation/cscec-ui-autotest/reports/metering260901/results.json"
)

ID_TOKEN = re.compile(r"\b([MF]\d{1,2}(?:\.\d{1,2})*)\b")
STATUS_LABEL = {"passed": "通过", "failed": "失败", "skipped": "跳过"}
CLASS_LABEL = {
    "ENTRY_MISSING": "入口缺失/实现差异",
    "ROLE_REQUIRED": "手工协同（待角色）",
    "DATA_REQUIRED": "待数据/流程",
    "NOT_AUTOMATABLE": "不可自动化（待专项）",
    "ENV_LIMITED": "环境受限（待复核）",
    "MANUAL": "手工协同",
    "SKIPPED": "跳过",
}
FALLBACK_NOTES = {
    "F12": "待数据/流程：需“租户内订阅→移出租户→再查”的流程与账号编排，列入手工协同",
    "M11.1": "手工协同：组件与 SDK 通用订阅回归空壳小节，代表性只读面已由 M11.1.1 验证",
    "M11.2": "手工协同：服务中心与组件详情展示回归空壳小节，代表性只读面已由 M11.2.1 验证",
    "M11.3": "手工协同：订单/流程/工单回归空壳小节，代表性只读面已由 M11.3.1 验证",
}


ANNOTATION_TEXTS = {
    "问题", "叠加", "没有sdk", "数量=永久有效", "仅订阅成功",
    "生效时间保持最早时间", "生效时间更新最新时间", "状态变为可用", "研发改数据库",
}


def is_annotation(text: str) -> bool:
    return text.strip() in ANNOTATION_TEXTS


def load_results() -> dict:
    if not RESULTS.exists():
        return {}
    data = json.loads(RESULTS.read_text(encoding="utf-8"))
    return data.get("results", {})


def status_tag(case_id: str, rec: dict | None) -> str:
    if rec is None:
        return "手工协同" if case_id in FALLBACK_NOTES else "待补齐"
    if rec["status"] == "passed":
        return "通过"
    if rec["status"] == "failed":
        return "失败"
    cls = rec.get("classification", "SKIPPED")
    return CLASS_LABEL.get(cls, "跳过")


def autom_tag(case_id: str, rec: dict | None) -> str:
    if rec is None:
        return "手工协同" if case_id in FALLBACK_NOTES else "可自动化待补齐"
    if rec["status"] in ("passed", "failed"):
        return "已实现自动化"
    cls = rec.get("classification", "SKIPPED")
    if cls == "ROLE_REQUIRED":
        return "手工协同（待角色）"
    if cls == "DATA_REQUIRED":
        return "待数据（流程/数据依赖）"
    if cls == "ENTRY_MISSING":
        return "入口缺失（实现差异）"
    if cls == "NOT_AUTOMATABLE":
        return "不可自动化"
    if cls == "ENV_LIMITED":
        return "环境受限"
    return "可自动化待补齐"


def build_note(case_id: str, rec: dict | None, annotations: list[str]) -> str:
    parts = []
    if annotations:
        parts.append("大纲批注：" + "；".join(annotations))
    if rec is None:
        fallback = FALLBACK_NOTES.get(case_id)
        parts.append(
            f"执行说明：{fallback or '本轮未覆盖，待后续补齐自动化或手工执行'}"
        )
        return "\n".join(parts)
    status = rec.get("status")
    if status == "passed":
        parts.append("执行说明：只读 UI 断言通过（执行结果独立记录，不软化失败）。")
    elif status == "failed":
        err = (rec.get("error") or "").strip().splitlines()
        parts.append("执行说明：自动化断言失败，需人工核实（环境数据问题 or 缺陷）。")
        if err:
            parts.append("失败摘要：" + " | ".join(err[-4:])[:900])
    else:
        cls = rec.get("classification", "SKIPPED")
        label = CLASS_LABEL.get(cls, cls)
        reason = (rec.get("skip_reason") or "").strip().replace("\n", " ")
        parts.append(f"执行说明：{label}。跳过原因：{reason[:600]}")
    parts.append(f"测试定位：{rec.get('nodeid', '')}")
    return "\n".join(parts)


results: dict = {}


def annotate(node: dict, prefix: str | None):
    """Recursively annotate; returns (new_node, total, executed, passed).

    Node classification:
    - title starts with an M/F id token -> nominal node:
        * with children -> section (recurse, prefix updates)
        * without children -> bare shell leaf (case id = its own token)
    - otherwise -> case leaf; its children are annotations attached to it
      and do NOT consume case indexes.
    """
    title = (node.get("title") or "").strip()
    children = node.get("children", {}).get("attached", [])
    new_node = {"id": node.get("id", ""), "title": title}

    notes_plain = ""
    try:
        notes_plain = node["notes"]["plain"]["content"]
    except Exception:
        pass

    own = ID_TOKEN.match(title)
    if not children and own:
        # bare shell leaf, e.g. "M11.1 组件与 SDK 通用订阅回归" / "F12 ..."
        case_id = own.group(1)
        rec = results.get(case_id)
        tag_status = status_tag(case_id, rec)
        tag_auto = autom_tag(case_id, rec)
        new_node["title"] = f"[{case_id}][{tag_auto}][{tag_status}] {title}"
        note = build_note(case_id, rec, [])
        if notes_plain:
            note = notes_plain + "\n" + note
        new_node["notes"] = {"plain": {"content": note}}
        total = 1
        executed = 1 if rec is not None else 0
        passed = 1 if (rec is not None and rec["status"] == "passed") else 0
        return new_node, total, executed, passed

    if children and (own or prefix is None and not own):
        # section node (module or section titles all start with an id token)
        if own:
            prefix = own.group(1)
        new_children = []
        total = executed = passed = 0
        leaf_idx = 0
        for ch in children:
            ch_title = (ch.get("title") or "").strip()
            ch_children = ch.get("children", {}).get("attached", [])
            ch_own = ID_TOKEN.match(ch_title)
            if ch_own:
                # section child or bare shell leaf
                new_ch, t, e, p = annotate(ch, prefix)
                total += t
                executed += e
                passed += p
                new_children.append(new_ch)
                continue
            # case leaf (annotations live in ch_children)
            leaf_idx += 1
            case_id = f"{prefix}.{leaf_idx}" if prefix else f"RAW.{leaf_idx}"
            rec = results.get(case_id)
            tag_status = status_tag(case_id, rec)
            tag_auto = autom_tag(case_id, rec)
            new_leaf = {
                "id": ch.get("id", ""),
                "title": f"[{case_id}][{tag_auto}][{tag_status}] {ch_title}",
            }
            annotations = [
                (a.get("title") or "").strip() for a in ch_children
            ]
            note = build_note(case_id, rec, annotations)
            try:
                ch_notes = ch["notes"]["plain"]["content"]
                note = ch_notes + "\n" + note
            except Exception:
                pass
            new_leaf["notes"] = {"plain": {"content": note}}
            new_children.append(new_leaf)
            total += 1
            if rec is not None:
                executed += 1
                if rec["status"] == "passed":
                    passed += 1
        if new_children:
            new_node["children"] = {"attached": new_children}
        if notes_plain and "notes" not in new_node:
            new_node["notes"] = {"plain": {"content": notes_plain}}
        return new_node, total, executed, passed

    # fallback: unknown shape, keep as-is
    if notes_plain:
        new_node["notes"] = {"plain": {"content": notes_plain}}
    return new_node, 0, 0, 0


def main() -> None:
    global results
    results = load_results()
    with zipfile.ZipFile(MASTER) as z:
        master = json.loads(z.read("content.json").decode("utf-8"))
    sheet = master[0]
    root = sheet["rootTopic"]

    new_root, total, executed, passed = annotate(root, None)
    stats = (
        f"执行汇总（{datetime.now().isoformat(timespec='seconds')}，PRE 环境，账号 20431644）："
        f"大纲用例 {total} 条；本轮执行 {executed} 条（通过 {passed}、"
        f"未过 {executed - passed}，含实现差异/环境受限项）；"
        "其余为标注项（待角色/待数据/入口缺失/不可自动化）。"
        "本文件为自动化测试用大纲（独立生成），未改动主大纲。"
    )
    old_notes = new_root.get("notes", {}).get("plain", {}).get("content", "")
    new_root["notes"] = {
        "plain": {"content": (old_notes + "\n" + stats).strip() if old_notes else stats}
    }

    # post-process: merge representative-case results into bare shell nodes
    SUB = {"M11.1": "M11.1.1", "M11.2": "M11.2.1", "M11.3": "M11.3.1"}
    SHELL_PAT = re.compile(r"\[(M11\.[123])\]")

    def merge_shell(node):
        title = node.get("title") or ""
        m = SHELL_PAT.match(title)
        if m:
            shell = m.group(1)
            sub_id = SUB.get(shell)
            sub = results.get(sub_id)
            if sub:
                st = STATUS_LABEL.get(sub.get("status"), sub.get("status"))
                extra = (
                    f"\n代表性只读验证（{sub_id}）：{st} —— "
                    f"{(sub.get('title') or '')[:80]}"
                )
                notes = node.get("notes", {}).get("plain", {}).get("content", "")
                node["notes"] = {"plain": {"content": notes + extra}}
        for ch in node.get("children", {}).get("attached", []):
            merge_shell(ch)

    merge_shell(new_root)

    out = [
        {
            "id": sheet.get("id", "sheet1"),
            "class": "sheet",
            "title": sheet.get("title", "测试大纲"),
            "rootTopic": new_root,
        }
    ]

    if TARGET.exists():
        backup = TARGET.with_suffix(".xmind.bak")
        shutil.copy2(TARGET, backup)
        print(f"backup old target -> {backup}")
    with zipfile.ZipFile(MASTER) as zin:
        entries = {n: zin.read(n) for n in zin.namelist() if n != "content.json"}
    entries["content.json"] = json.dumps(out, ensure_ascii=False, indent=1).encode(
        "utf-8"
    )
    with zipfile.ZipFile(TARGET, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, blob in entries.items():
            zout.writestr(name, blob)
    print(f"written: {TARGET}")
    print(f"stats: total={total} executed={executed} passed={passed}")

    # unmatched cases for the report
    def collect_ids(node, out_list):
        title = node.get("title") or ""
        m = re.match(r"\[([MF][\d.]+)\]", title)
        if m:
            out_list.append(m.group(1))
        for ch in node.get("children", {}).get("attached", []):
            collect_ids(ch, out_list)

    ids: list[str] = []
    collect_ids(new_root, ids)
    unmatched = [c for c in results if c not in ids]
    print("结果中未落入大纲的编号:", unmatched or "无")
    Path(r"D:/Automation/cscec-ui-autotest/reports/metering260901/unmatched.json").write_text(
        json.dumps({"outline_cases": len(ids), "unmatched": unmatched},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
