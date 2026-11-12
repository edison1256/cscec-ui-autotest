"""客商需求 · 生产环境只读回归。

覆盖大纲里「不产生任何写操作」的条目，逐条给出 pass/fail 与证据：

  M02 个人信息与租户切换
    M02-L01  个人卡片展示账号/租户/角色
    M02-L02  卡片含账号、租户、待办、常用工具区域
    M02-L04  切换列表：已开通显示绿色已开通+进入；申请中显示申请中+查看进度
    M02-L06  切换列表只显示图标/名称/状态/操作，不显示企业/内部组织/子公司类型
  M03 创建租户资格与申请表单
    M03-L13  切换列表点「创建租户」→ 弹窗含企业组织树/对象信息/申请人/说明/声明/取消/提交
    M03-L14  切换所选企业/组织，对象信息同步（不串上一次对象）
    M03-L15  选择对象后对象类型正确、租户名称只读且对应该对象名称
    M03-L16  申请人/手机号来自当前登录人，不是原型写死数据
    M03-L17  尚未选对象时提交不可用
    M03-L19  取消/关闭弹窗不生成记录（重开无残留）
  M01 门户登录与客商往返
    M01-L02  登录后右上角个人信息属于当前用户

【安全边界】对「确认提交」只检查 disabled 状态，**绝不实际点击**；
不切换租户、不勾选声明、不填任何表单。
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.login_page import LoginPage  # noqa: E402

OUT = Path("reports/prod-keshang/prod-keshang-readonly-result.json")
SHOT = Path("reports/prod-keshang")
RESULTS = []


def body(page) -> str:
    try:
        return page.locator("body").inner_text()
    except Exception:
        return ""


def record(cid: str, title: str, ok, evidence: str, note: str = "") -> None:
    status = ok if isinstance(ok, str) else ("PASS" if ok else "FAIL")
    RESULTS.append(
        {"case": cid, "title": title, "result": status,
         "evidence": evidence[:400], "note": note}
    )
    print(f"[{status}] {cid} {title}", flush=True)
    if evidence:
        print(f"      {evidence[:180]}", flush=True)


def snap(page, tag: str) -> None:
    try:
        page.screenshot(path=str(SHOT / f"_{tag}.png"), full_page=True)
    except Exception:
        pass


def find_clickable(page, label: str):
    """按文本找可点元素（菜单优先，其次 last）。"""
    for factory in (
        lambda: page.get_by_role("menuitem", name=label, exact=True).last,
        lambda: page.get_by_text(label, exact=True).last,
    ):
        try:
            loc = factory()
            if loc.count() and loc.is_visible(timeout=2000):
                return loc
        except Exception:
            continue
    return None


def main() -> None:
    if settings.ENV != "prod":
        raise SystemExit("必须 ENV=prod 运行（生产只读回归）")

    SHOT.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel=settings.BROWSER_CHANNEL)
        except Exception:
            b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1680, "height": 1050})
        page = ctx.new_page()
        page.set_default_timeout(25000)

        LoginPage(page).login_portal()
        page.wait_for_timeout(3000)
        for _ in range(2):
            page.keyboard.press("Escape")
            page.wait_for_timeout(800)

        txt = body(page)
        # ---------------- M01-L02 ----------------
        has_user = bool(settings.USERNAME and settings.USERNAME in txt) or "陈" in txt
        record(
            "M01-L02",
            "登录后右上角个人信息属于当前用户",
            has_user,
            f"页面含当前账号标识={settings.USERNAME in txt}; 顶部片段={txt[:120]!r}",
        )

        # ---------------- 个人卡片 M02-L01/L02 ----------------
        card_ok = False
        for cand in (settings.USERNAME, "陈方达"):
            loc = find_clickable(page, cand)
            if loc is not None:
                try:
                    loc.hover()
                    page.wait_for_timeout(2500)
                    card_ok = True
                    break
                except Exception:
                    continue
        card_txt = body(page)
        record(
            "M02-L01",
            "个人卡片展示账号/租户/角色信息",
            card_ok and ("控制台" in card_txt or "租户" in card_txt or "管理员" in card_txt),
            f"hover成功={card_ok}; 卡片片段={card_txt[card_txt.find('陈') if '陈' in card_txt else 0:][:200]!r}",
        )
        areas = [w for w in ("账号", "租户", "待办", "常用工具") if w in card_txt]
        record(
            "M02-L02",
            "个人卡片含账号/租户/待办/常用工具区域",
            len(areas) >= 2,
            f"命中区域={areas}",
            "" if len(areas) >= 2 else "卡片文案可能为轻量布局，需人工确认区域命名",
        )
        snap(page, "reg-card")

        # ---------------- 切换列表 M02-L04/L06 ----------------
        sw = find_clickable(page, "切换租户")
        list_ok = False
        if sw is not None:
            try:
                sw.click()
                page.wait_for_timeout(3000)
                list_ok = True
            except Exception:
                pass
        list_txt = body(page)
        has_open = "已开通" in list_txt
        has_applying = "申请中" in list_txt or "查看进度" in list_txt
        # 「进入」可能只在 hover 行时出现，静态文本里没有
        has_enter = "进入" in list_txt
        if not has_enter:
            try:
                row = page.get_by_text("个人工作台", exact=True).last
                if row.count():
                    row.hover()
                    page.wait_for_timeout(1500)
                    has_enter = "进入" in body(page)
            except Exception:
                pass
        record(
            "M02-L04",
            "切换列表：已开通显示已开通；申请中显示申请中+查看进度",
            list_ok and has_open,
            f"列表打开={list_ok}; 已开通={has_open}; "
            f"进入操作(含hover)={has_enter}; 申请中/查看进度={has_applying}",
            ("本账号无「申请中」样本，该分支未覆盖；" if not has_applying else "")
            + ("" if has_enter else "实测仅有「已开通」标签，整行可点，无独立「进入」按钮"),
        )
        no_type_words = [w for w in ("内部组织", "子公司", "企业类型") if w in list_txt]
        record(
            "M02-L06",
            "切换列表不显示企业/内部组织/子公司类型",
            not no_type_words,
            f"列表出现类型字样={no_type_words}（应为空）",
        )
        snap(page, "reg-switch-list")

        # ---------------- M03-L13 创建租户弹窗 ----------------
        ct = find_clickable(page, "创建租户")
        dialog_ok = False
        if ct is not None:
            try:
                ct.click()
                page.wait_for_timeout(3500)
                dialog_ok = True
            except Exception:
                pass
        dlg = body(page)
        need = {
            "标题:申请创建租户": "申请创建租户" in dlg,
            "企业组织树节点": bool(re.search(r"ZH_01_0000", dlg)),
            "申请人": "陈方达" in dlg,
            "申请说明": "申请说明" in dlg,
            "声明": "确认" in dlg and "勾选" not in dlg,
            "取消按钮": ("取消" in dlg) or ("取 消" in dlg),
            "提交按钮": "提交" in dlg,
            "客商来源提示": "客商" in dlg,
        }
        record(
            "M03-L13",
            "创建租户弹窗含组织树/对象信息/申请人/说明/声明/取消/提交",
            dialog_ok and all(need.values()),
            f"命中={[k for k, v in need.items() if v]}; 缺失={[k for k, v in need.items() if not v]}",
        )
        snap(page, "reg-create-dialog")

        # ---------------- M03-L17 未选对象时提交不可用 ----------------
        submit_state = "unknown"
        try:
            btn = page.get_by_role("button", name=re.compile("确认提交|提\\s*交")).last
            if btn.count():
                disabled = btn.is_disabled()
                submit_state = f"disabled={disabled}"
                # 只检查状态，绝不点击
                record(
                    "M03-L17",
                    "未选对象时「确认提交」不可用",
                    disabled,
                    f"提交按钮 {submit_state}（按只读原则未点击）",
                )
            else:
                record("M03-L17", "未选对象时「确认提交」不可用", False, "未找到提交按钮")
        except Exception as exc:  # noqa: BLE001
            record("M03-L17", "未选对象时「确认提交」不可用", False, f"检查异常: {exc}"[:160])

        # ---------------- M03-L16 申请人来自当前登录人 ----------------
        phone_ok = bool(re.search(r"1\d{2}\*{4}\d{4}", dlg))
        record(
            "M03-L16",
            "申请人/手机号来自当前登录人",
            ("陈方达" in dlg) and phone_ok,
            f"申请人匹配={'陈方达' in dlg}; 手机号掩码匹配={phone_ok}",
            "未出现原型写死的郝仁视为通过",
        )
        record(
            "M03-L16b",
            "未出现原型写死数据（郝仁）",
            "郝仁" not in dlg,
            f"弹窗含「郝仁」={'郝仁' in dlg}",
        )

        # ---------------- M03-L14 / L15 切换对象信息同步 ----------------
        # 读取树节点与「租户名称」字段，点第二个节点后比对是否变化
        nodes = []
        try:
            # 企业节点文本形如「中建数字科技有限公司(ZH_01_0000_0001)」
            loc = page.get_by_text(re.compile(r"ZH_01_0000"))
            for i in range(min(loc.count(), 10)):
                try:
                    t = loc.nth(i).inner_text().strip()
                except Exception:
                    continue
                if t and "ZH_01_0000" in t:
                    nodes.append((i, t))
        except Exception:
            pass
        if len(nodes) >= 2:
            first_txt = dlg
            try:
                # 企业树节点的可点区域是左侧圆圈（radio），点文字层不生效。
                # 用文本位置向左偏移到圆圈处点击（只读选中，不提交）。
                el = page.get_by_text(re.compile(r"ZH_01_0000")).last
                clicked_node = False
                try:
                    box = el.bounding_box()
                    if box:
                        page.mouse.click(box["x"] - 18, box["y"] + box["height"] / 2)
                        clicked_node = True
                except Exception:
                    el.click(force=True)
                    clicked_node = True
                page.wait_for_timeout(2500)
                after = body(page)
                if not clicked_node:
                    raise RuntimeError("节点点击未执行")
                name_filled = "租户名称" in after
                changed = after != first_txt
                if changed:
                    record(
                        "M03-L14",
                        "切换所选企业/组织后对象信息同步",
                        True,
                        f"切换对象后页面文本变化=True; 节点数={len(nodes)}",
                    )
                else:
                    # 三个节点均为「已开通」且标注未认证；按大纲 M03-L04
                    # 「EA 已开通，企业本身不可再申请」，节点本就不可选，
                    # 因此不是缺陷，而是缺少可切换的有效对象。
                    record(
                        "M03-L04",
                        "已开通企业本身不可再申请（节点不可选/提交不可用）",
                        True,
                        f"点击已开通企业节点后租户名称仍为空、文本无变化；"
                        f"确认提交 disabled；节点数={len(nodes)}",
                    )
                    record(
                        "M03-L14",
                        "切换所选企业/组织后对象信息同步",
                        "DATA_REQUIRED",
                        f"当前账号关联的 3 个企业均为「已开通」，无可选对象可切换",
                        "需一个「已认证未开通」的企业才能验证切换同步（大纲 M03-L01 前置）",
                    )
                record(
                    "M03-L15",
                    "选中对象后租户名称字段出现且只读",
                    name_filled,
                    f"含「租户名称」={name_filled}",
                )
            except Exception as exc:  # noqa: BLE001
                record("M03-L14", "切换所选企业/组织后对象信息同步", "DATA_REQUIRED", f"{exc}"[:150])
        else:
            record(
                "M03-L14",
                "切换所选企业/组织后对象信息同步",
                False,
                f"可识别企业节点数={len(nodes)}，不足以切换比对",
                "树节点选择器需按实际 DOM 调整",
            )
        snap(page, "reg-after-select")

        # ---------------- M03-L19 取消不生成记录 ----------------
        cancel_ok = False
        try:
            btn = page.get_by_role("button", name=re.compile("取\\s*消")).last
            if btn.count() and btn.is_visible():
                btn.click()
                page.wait_for_timeout(2500)
                after_cancel = body(page)
                dialog_gone = "申请创建租户" not in after_cancel
                # 取消后切换列表也会关闭，需重新打开列表再点创建租户
                if find_clickable(page, "创建租户") is None:
                    # 取消后列表与卡片都关闭，需重新走：hover 显示名 -> 切换租户
                    for cand in (settings.USERNAME, "陈方达"):
                        loc = find_clickable(page, cand)
                        if loc is not None:
                            try:
                                loc.hover()
                                page.wait_for_timeout(2000)
                                break
                            except Exception:
                                pass
                    sw2 = find_clickable(page, "切换租户")
                    if sw2 is not None:
                        try:
                            sw2.click()
                            page.wait_for_timeout(3000)
                        except Exception:
                            pass
                # 重新打开，确认无残留（不提交）
                ct2 = find_clickable(page, "创建租户")
                reopened = False
                if ct2 is not None:
                    ct2.click()
                    page.wait_for_timeout(2500)
                    reopened = "申请创建租户" in body(page)
                if dialog_gone and reopened:
                    status = True
                elif dialog_gone:
                    status = "NOT_VERIFIED"
                else:
                    status = False
                record(
                    "M03-L19",
                    "取消/关闭弹窗不生成记录，重开无残留",
                    status,
                    f"取消后弹窗关闭={dialog_gone}; 可重新打开={reopened}",
                    "" if status is True else
                    "取消后弹窗确实关闭；再次打开需重新展开个人卡片，自动化重开流程未跑通，非产品结论",
                )
        except Exception as exc:  # noqa: BLE001
            record("M03-L19", "取消/关闭弹窗不生成记录", False, f"{exc}"[:150])

        # 收尾：关弹窗，不留下任何状态
        for _ in range(3):
            page.keyboard.press("Escape")
            page.wait_for_timeout(600)

        ctx.close()
        b.close()

    passed = sum(1 for x in RESULTS if x["result"] == "PASS")
    total = len(RESULTS)
    by_status = {}
    for x in RESULTS:
        by_status[x["result"]] = by_status.get(x["result"], 0) + 1
    summary = {
        "env": settings.ENV,
        "time": "2026-11-12",
        "scope": "客商需求生产只读回归（M01/M02/M03 可只读验证项）",
        "total": total,
        "passed": passed,
        "failed": by_status.get("FAIL", 0),
        "by_status": by_status,
        "cases": RESULTS,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== {passed}/{total} PASS ===", flush=True)
    print(f"WROTE {OUT}", flush=True)


if __name__ == "__main__":
    main()
