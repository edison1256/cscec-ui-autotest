"""UAT 环境客商功能侦察（只读）。

Phase 0 目的：生产与 UAT 的客商形态可能不同（生产控制台无「客商管理」，UAT 有），
不确认入口、账号权限、可用企业状态就写用例会写错。

侦察六项：
  1. 控制台左侧菜单全量 + 是否含「客商管理」及其子项
  2. 门户「个人卡片 -> 切换租户 -> 创建租户」链路是否可用
  3. 创建租户弹窗内的企业列表与各自状态（已认证/未开通/申请中/已开通）
  4. ADMIN 账号能否登录、权限管理下有哪些子项
  5. 主账号是否已关联可申请企业
  6. 审批中心是否可见租户申请类待办

严格只读：只展开菜单、打开弹窗、读取文本；不勾声明、不点确认提交、不切换租户。
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.login_page import LoginPage  # noqa: E402

OUT = Path("reports/keshang/_uat-recon.json")
SHOT = Path("reports/keshang")

STATUS_WORDS = ("已开通", "未开通", "申请中", "未认证", "已认证", "审核中")


def body_text(page, limit: int = 3000) -> str:
    try:
        return page.locator("body").inner_text()[:limit]
    except Exception:
        return ""


def short_lines(txt: str, lo: int = 2, hi: int = 20) -> list[str]:
    return [x.strip() for x in txt.splitlines() if x.strip() and lo <= len(x.strip()) <= hi]


def snap(page, tag: str) -> None:
    try:
        SHOT.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOT / f"_uat-{tag}.png"), full_page=True)
    except Exception:
        pass


def click_text(page, label: str, wait_ms: int = 2500) -> bool:
    for factory in (
        lambda: page.get_by_role("menuitem", name=label, exact=True).last,
        lambda: page.get_by_text(label, exact=True).last,
    ):
        try:
            loc = factory()
            if loc.count() and loc.is_visible(timeout=2500):
                loc.click()
                page.wait_for_timeout(wait_ms)
                return True
        except Exception:
            continue
    return False


def recon_console(page) -> dict:
    """控制台：菜单全量 + 客商管理是否存在。"""
    info = {"url": page.url[:200]}
    txt = body_text(page)
    info["menu_lines"] = short_lines(txt, 2, 12)[:60]
    info["has_keshang"] = "客商" in txt

    # 逐个展开一级菜单，收集新出现的叶子
    tops = [x for x in info["menu_lines"] if x in {
        "资源管理", "订阅服务", "审批流程", "评价中心", "系统配置", "流程",
        "订单中心", "工单中心", "运维监控", "运营管理", "权限管理", "计量统计",
    }]
    info["top_menus_found"] = tops
    expanded = {}
    for top in tops:
        before = set(short_lines(body_text(page), 2, 12))
        if click_text(page, top, 2000):
            after = set(short_lines(body_text(page), 2, 12))
            new = sorted(after - before)
            if new:
                expanded[top] = new[:15]
    info["expanded"] = expanded
    info["keshang_menu_present"] = any("客商" in k or any("客商" in v for v in vals)
                                       for k, vals in expanded.items())
    return info


def recon_portal(page) -> dict:
    """门户：个人卡片 -> 切换租户 -> 创建租户弹窗。"""
    info = {"url": page.url[:200]}
    txt = body_text(page)
    info["landing_has_keshang"] = "客商" in txt

    # 打开个人卡片
    hovered = False
    for cand in (settings.keshang_username, settings.USERNAME, "陈方达"):
        if not cand:
            continue
        try:
            loc = page.get_by_text(cand, exact=True).first
            if loc.count() and loc.is_visible(timeout=2500):
                loc.hover()
                page.wait_for_timeout(2200)
                hovered = True
                break
        except Exception:
            continue
    info["card_hovered"] = hovered

    # 点切换租户
    info["switch_opened"] = click_text(page, "切换租户", 2800)
    switch_txt = body_text(page)
    info["switch_lines"] = short_lines(switch_txt, 2, 24)[:40]
    info["switch_status_words"] = [w for w in STATUS_WORDS if w in switch_txt]
    info["has_create_tenant"] = "创建租户" in switch_txt
    snap(page, "switch")

    # 打开创建租户弹窗（只读）
    if info["has_create_tenant"]:
        if click_text(page, "创建租户", 3200):
            dlg = body_text(page)
            info["dialog_opened"] = "申请创建租户" in dlg
            info["dialog_text"] = dlg[:1800]
            info["dialog_status_words"] = [w for w in STATUS_WORDS if w in dlg]
            # 企业节点：把「企业名(ZH_xxx)」与紧随其后的状态词配对。
            # 树节点渲染形如：
            #   中建数字科技有限公司(ZH_01_0000_0001)
            #   已开通
            #   未认证
            lines = [x.strip() for x in dlg.splitlines() if x.strip()]
            enterprises = []
            for i, ln in enumerate(lines):
                if "ZH_" in ln and "(" in ln:
                    tail = lines[i + 1: i + 4]
                    states = [w for w in STATUS_WORDS if any(w in t for t in tail)]
                    enterprises.append({"label": ln[:60], "states": states})
            info["enterprises"] = enterprises[:15]
            info["enterprise_candidates"] = sorted({
                m.group(0)
                for m in re.finditer(r"[\u4e00-\u9fa5A-Za-z0-9（）()]{4,40}", dlg)
                if ("ZH_" in m.group(0) or "公司" in m.group(0) or "集团" in m.group(0))
            })[:20]
            # 提交按钮状态（只读不点）
            try:
                btn = page.get_by_role("button", name=re.compile("确认提交|提\\s*交")).last
                info["submit_disabled"] = btn.is_disabled() if btn.count() else None
            except Exception:
                info["submit_disabled"] = None
            snap(page, "create-dialog")
            for _ in range(3):
                page.keyboard.press("Escape")
                page.wait_for_timeout(600)
    return info


def recon_admin(browser) -> dict:
    """管理员：能否登录 + 权限管理/审批中心可见性。"""
    info = {}
    if not settings.ADMIN_USERNAME:
        return {"error": "ADMIN_USERNAME 未配置"}
    ctx = browser.new_context(viewport={"width": 1680, "height": 1050}, ignore_https_errors=True)
    page = ctx.new_page()
    page.set_default_timeout(25000)
    try:
        LoginPage(page).login(
            username=settings.ADMIN_USERNAME,
            password=settings.ADMIN_PASSWORD,
        )
        page.wait_for_timeout(3000)
        url = page.url.lower()
        # login() 在凭据错误时不一定抛异常（页面停留在 CAS 登录页），
        # 必须用最终 URL 判定，否则会把失败当成功。
        if "cas/login" in url or "idaas" in url or "passport/login" in url:
            info["login_ok"] = False
            info["error"] = "登录后仍停留在认证页，账号或密码可能无效"
            info["url"] = page.url[:200]
            snap(page, "admin-failed")
            ctx.close()
            return info
        info["login_ok"] = True
        info["url"] = page.url[:200]
        txt = body_text(page)
        info["has_keshang"] = "客商" in txt
        info["menu_lines"] = short_lines(txt, 2, 12)[:50]

        # 权限管理子项
        click_text(page, "权限管理", 2200)
        perm = body_text(page)
        info["permission_lines"] = short_lines(perm, 2, 12)[:40]

        # 客商管理页面（UAT 独有，生产无此菜单）
        if click_text(page, "客商管理", 3500):
            ksh = body_text(page)
            info["keshang_url"] = page.url[:220]
            info["keshang_body"] = ksh[:1500]
            info["keshang_lines"] = short_lines(ksh, 2, 20)[:50]
            info["keshang_status_words"] = [w for w in STATUS_WORDS if w in ksh]
            snap(page, "keshang-manage")

        # 审批中心（工作台卡片或菜单）
        click_text(page, "审批流程", 2000)
        flow = body_text(page)
        info["flow_lines"] = short_lines(flow, 2, 14)[:30]
        info["has_tenant_apply_word"] = any(
            w in flow for w in ("租户申请", "创建租户", "租户审批")
        )
        snap(page, "admin")
    except Exception as exc:  # noqa: BLE001
        info["login_ok"] = False
        info["error"] = f"{type(exc).__name__}: {exc}"[:300]
        info["url_at_failure"] = page.url[:200]
        snap(page, "admin-failed")
    finally:
        ctx.close()
    return info


def main() -> None:
    if settings.ENV != "uat":
        raise SystemExit("必须 ENV=uat 运行（Phase 0 侦察 UAT）")

    SHOT.mkdir(parents=True, exist_ok=True)
    r = {
        "env": settings.ENV,
        "console_base": settings.CONSOLE_BASE_URL,
        "portal_base": settings.PORTAL_BASE_URL,
        "applicant": settings.keshang_username[:3] + "***" if settings.keshang_username else None,
        "uses_keshang_account": settings.uses_keshang_account,
        "admin_configured": bool(settings.ADMIN_USERNAME),
    }

    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel=settings.BROWSER_CHANNEL)
        except Exception:
            b = p.chromium.launch(headless=True)

        # --- 1. 控制台（申请人身份）---
        ctx = b.new_context(viewport={"width": 1680, "height": 1100}, ignore_https_errors=True)
        page = ctx.new_page()
        page.set_default_timeout(25000)
        try:
            LoginPage(page).login()
            page.wait_for_timeout(3000)
            r["console"] = recon_console(page)
            print("console ok, has客商:", r["console"]["has_keshang"], flush=True)
            print("  expanded:", json.dumps(r["console"]["expanded"], ensure_ascii=False)[:400], flush=True)
            snap(page, "console")
        except Exception as exc:  # noqa: BLE001
            r["console"] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
            print("console FAILED:", r["console"]["error"], flush=True)
        ctx.close()

        # --- 2. 门户（申请人身份）---
        ctx2 = b.new_context(viewport={"width": 1680, "height": 1100}, ignore_https_errors=True)
        p2 = ctx2.new_page()
        p2.set_default_timeout(25000)
        try:
            LoginPage(p2).login_portal()
            p2.wait_for_timeout(3000)
            for _ in range(2):
                p2.keyboard.press("Escape")
                p2.wait_for_timeout(700)
            r["portal"] = recon_portal(p2)
            print("portal ok, switch_opened:", r["portal"].get("switch_opened"),
                  "create_tenant:", r["portal"].get("has_create_tenant"), flush=True)
            print("  status_words:", r["portal"].get("dialog_status_words"), flush=True)
        except Exception as exc:  # noqa: BLE001
            r["portal"] = {"error": f"{type(exc).__name__}: {exc}"[:300]}
            print("portal FAILED:", r["portal"]["error"], flush=True)
        ctx2.close()

        # --- 3. 管理员 ---
        r["admin"] = recon_admin(b)
        print("admin login_ok:", r["admin"].get("login_ok"),
              "has客商:", r["admin"].get("has_keshang"), flush=True)

        b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWROTE {OUT}", flush=True)


if __name__ == "__main__":
    main()
