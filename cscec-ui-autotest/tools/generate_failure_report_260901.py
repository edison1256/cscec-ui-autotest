"""Generate a detailed failure report for metering-subscription 260901.

Inputs:
- reports/metering260901/results.json           (current run)
- optional previous run json (for delta comparison)
- master outline xmind (to quote the outline expectation per case)

Output: markdown report with per-case details, root-cause classification,
delta vs previous run, and action suggestions.

Usage:
  python tools/generate_failure_report_260901.py \
      --source "D:/Doc/一体化/用例/计量订阅260901测试大纲.xmind" \
      --results reports/metering260901/results.json \
      --previous reports/metering260901/results_20261010_final.json \
      --output "D:/Doc/一体化/用例/计量订阅260901失败报告_20261012.md"
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

ID_TOKEN = re.compile(r"\b([MF]\d{1,2}(?:\.\d{1,2})*)\b")
ANNOTATION_TEXTS = {
    "问题", "叠加", "没有sdk", "数量=永久有效", "仅订阅成功",
    "生效时间保持最早时间", "生效时间更新最新时间", "状态变为可用", "研发改数据库",
}

# Root-cause classification by error/skip text keywords (first match wins)
ROOT_CAUSE_RULES: list[tuple[str, str]] = [
    ("ENTRY_MISSING", "实现差异·控件/入口缺失"),
    ("Bad Gateway", "环境故障·子应用 502"),
    ("qiankun", "环境故障·子应用 502"),
    ("无法切换到", "环境/会话·租户切换失败"),
    ("菜单项不可点击", "环境/时序·导航失败"),
    ("缺失表头", "页面形态变化·表头契约不符"),
    ("未渲染", "环境/时序·列表未渲染"),
    ("锚点", "数据漂移·锚点数据变化"),
    ("assert False", "数据/上下文·断言前置失败"),
    ("Timeout", "环境/时序·超时"),
]


def classify(text: str) -> str:
    for kw, label in ROOT_CAUSE_RULES:
        if kw in text:
            return label
    return "待人工核实"


def load_outline(source: Path) -> dict[str, str]:
    """Return {case_id: outline_text} using nominal numbering."""
    with zipfile.ZipFile(source) as z:
        data = json.loads(z.read("content.json").decode("utf-8"))
    out: dict[str, str] = {}

    def walk(node, prefix: str | None):
        title = (node.get("title") or "").strip()
        children = node.get("children", {}).get("attached", [])
        own = ID_TOKEN.match(title)
        if not children and own:
            out.setdefault(own.group(1), title)
            return
        if children:
            if own:
                prefix = own.group(1)
            idx = 0
            for ch in children:
                ch_title = (ch.get("title") or "").strip()
                ch_children = ch.get("children", {}).get("attached", [])
                ch_own = ID_TOKEN.match(ch_title)
                if ch_own:
                    walk(ch, prefix)
                    continue
                if ch_title in ANNOTATION_TEXTS:
                    continue
                idx += 1
                cid = f"{prefix}.{idx}" if prefix else None
                if cid:
                    out.setdefault(cid, ch_title)
                # annotations under this case are ignored for id purposes
            return

    walk(data[0]["rootTopic"], None)
    return out


def load_results(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("results", {})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--previous", default=None)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    outline = load_outline(Path(args.source))
    results = load_results(Path(args.results))
    previous = load_results(Path(args.previous)) if args.previous and Path(args.previous).exists() else {}

    def dkey(cid: str):
        try:
            return [int(p) for p in cid.lstrip("MF").split(".")]
        except Exception:
            return [999]

    # distribution
    dist: dict[str, int] = {}
    for cid, r in results.items():
        if not isinstance(r, dict):
            continue
        s = r["status"]
        key = s if s != "skipped" else f"skipped[{r.get('classification', 'SKIPPED')}]"
        dist[key] = dist.get(key, 0) + 1

    fails = {c: r for c, r in results.items() if isinstance(r, dict) and r["status"] == "failed"}

    # root cause buckets
    buckets: dict[str, list[str]] = OrderedDict()
    for cid in sorted(fails, key=dkey):
        rc = classify((fails[cid].get("error") or ""))
        buckets.setdefault(rc, []).append(cid)

    # delta vs previous
    new_fail, still_fail, fixed = [], [], []
    for cid, r in fails.items():
        prev = previous.get(cid)
        if prev is None:
            new_fail.append(cid)
        elif isinstance(prev, dict) and prev.get("status") == "failed":
            still_fail.append(cid)
        else:
            new_fail.append(cid)  # previously not failed (or no record)
    for cid, r in results.items():
        if not isinstance(r, dict) or r["status"] != "failed":
            prev = previous.get(cid)
            if isinstance(prev, dict) and prev.get("status") == "failed":
                fixed.append(cid)

    lines: list[str] = []
    A = lines.append
    A(f"# 计量订阅 260901 Pre 环境失败报告")
    A("")
    A(f"- **执行时间**：{datetime.now().strftime('%Y-%m-%d %H:%M')}（PRE 环境，账号 20431644）")
    A(f"- **用例总数**：{len([c for c in results if isinstance(results[c], dict)])}")
    A(f"- **失败**：{len(fails)}；**对比上次**：新增失败 {len(new_fail)}、未修复 {len(still_fail)}、本轮修复 {len(fixed)}")
    A("")
    A("## 一、结果分布")
    A("")
    A("| 分类 | 数量 |")
    A("|---|---|")
    for k, v in sorted(dist.items(), key=lambda x: -x[1]):
        A(f"| {k} | {v} |")
    A("")

    A("## 二、失败根因分类")
    A("")
    A("| 根因 | 数量 | 用例编号 |")
    A("|---|---|---|")
    for rc, cids in buckets.items():
        A(f"| {rc} | {len(cids)} | {', '.join(cids[:12])}{' …' if len(cids) > 12 else ''} |")
    A("")

    A("## 三、失败用例明细")
    A("")
    for cid in sorted(fails, key=dkey):
        r = fails[cid]
        err = (r.get("error") or "").strip()
        outline_text = outline.get(cid, "<未在大纲中匹配到>")
        rc = classify(err)
        # key assertion lines
        key_lines = [l.strip() for l in err.splitlines() if l.strip().startswith(("E ", "E\t"))]
        if not key_lines:
            key_lines = [l.strip() for l in err.splitlines()[-6:]]
        A(f"### {cid} — {outline_text[:90]}")
        A("")
        A(f"- **根因分类**：{rc}")
        A(f"- **用例名**：`{(r.get('title') or '')[:110]}`")
        A(f"- **节点**：`{r.get('nodeid', '')}`")
        A(f"- **断言/错误关键行**：")
        for kl in key_lines[:6]:
            A(f"  ```")
            A(f"  {kl[:300]}")
            A(f"  ```")
        A(f"- **建议动作**：{suggest(rc, cid)}")
        A("")

    A("## 四、增量对比（vs 上次执行）")
    A("")
    A(f"- **本轮修复（上次失败→本轮通过/跳过）**：{', '.join(sorted(fixed, key=dkey)) or '无'}")
    A(f"- **新增失败（上次非失败→本轮失败）**：{', '.join(sorted(new_fail, key=dkey)) or '无'}")
    A(f"- **持续失败（两轮均失败）**：{', '.join(sorted(still_fail, key=dkey)) or '无'}")
    A("")
    A("## 五、处理建议")
    A("")
    A("1. **实现差异类**（ENTRY_MISSING）：产品确认筛选控件终态（可用状态/订阅应用/服务模式/租户编码/租户名称），同步修订大纲或提缺陷单。")
    A("2. **数据漂移类**：在数据稳定窗口（无其他团队改数）复跑；必要时申请固定测试数据。")
    A("3. **页面形态类**：确认是否为最新交付版本；表头契约随版本更新维护。")
    A("4. **环境类**：pre 子应用 502 为间歇故障，重跑可恢复；若高频出现需运维介入。")
    A("")
    A("> 声明：本报告基于 PRE 共享环境当次执行结果，数据随时间漂移；失败项请结合截图与网络响应复核。")

    out_path = Path(args.output)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[报告已生成] {out_path}")
    print(f"失败 {len(fails)} 条；新增 {len(new_fail)}；持续 {len(still_fail)}；修复 {len(fixed)}")
    for rc, cids in buckets.items():
        print(f"  {rc}: {len(cids)}")


def suggest(rc: str, cid: str) -> str:
    if rc.startswith("实现差异"):
        return "产品/开发确认控件终态；如为需求变更则更新大纲，如为实现缺失则提缺陷单"
    if rc.startswith("数据漂移"):
        return "在数据稳定窗口复跑；必要时申请固定测试数据或改用接口层数据校验"
    if rc.startswith("页面形态"):
        return "确认为最新交付版；按新版表头契约更新断言（或提缺陷单说明字段缺失）"
    if rc.startswith("环境故障"):
        return "重跑；若高频复现则报运维检查 pre 子应用/网关"
    if rc.startswith("环境/时序") or rc.startswith("环境/会话"):
        return "重跑并观察；持续失败则检查会话/网络稳定性"
    return "人工打开对应页面复核，结合截图与网络响应定位"


if __name__ == "__main__":
    main()
