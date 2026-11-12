"""生产环境客商入口探测（门户侧）——纯只读。

大纲指引：
  M02 个人信息与租户切换：个人卡片含账号/租户/待办/常用工具；切换列表含状态与操作
  M03 创建租户：**在切换租户列表点击「创建租户」** 打开企业组织树弹窗

所以客商入口应在「工作台/门户右上角个人卡片 → 切换租户 → 创建租户」，
而不是控制台左侧菜单。

边界：只 hover/点开卡片与列表，不提交任何申请，不切换租户。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.login_page import LoginPage  # noqa: E402

OUT = Path("reports/prod-keshang/_probe_portal.json")
SHOT = Path("reports/prod-keshang")


def body(page) -> str:
    try:
        return page.locator("body").inner_text()
    except Exception:
        return ""


def snap(page, tag: str) -> dict:
    txt = body(page)
    d = {
        "url": page.url[:160],
        "body_head": txt[:1500],
        "has_keshang": "客商" in txt,
        "has_create_tenant": "创建租户" in txt,
        "has_switch": "切换租户" in txt,
        "has_cert": any(w in txt for w in ("认证", "已认证", "未认证")),
        "has_applying": "申请中" in txt,
    }
    try:
        page.screenshot(path=str(SHOT / f"_p-{tag}.png"), full_page=True)
    except Exception:
        pass
    return d


def main() -> None:
    if settings.ENV != "prod":
        raise SystemExit("必须 ENV=prod")

    SHOT.mkdir(parents=True, exist_ok=True)
    r = {"env": settings.ENV, "steps": {}}

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

        r["steps"]["landing"] = snap(page, "landing")
        print("landing:", r["steps"]["landing"]["url"], flush=True)
        print("  has客商:", r["steps"]["landing"]["has_keshang"], flush=True)

        # 1) hover 右上角显示名，打开个人卡片
        opened = False
        for cand in (settings.USERNAME, "陈方达"):
            try:
                loc = page.get_by_text(cand, exact=True).first
                if loc.count() and loc.is_visible(timeout=2500):
                    loc.hover()
                    page.wait_for_timeout(2500)
                    opened = True
                    break
            except Exception:
                continue
        r["steps"]["card"] = snap(page, "card")
        r["card_hovered"] = opened
        print("  card hovered:", opened, "| has客商:", r["steps"]["card"]["has_keshang"],
              "| has创建租户:", r["steps"]["card"]["has_create_tenant"], flush=True)

        # 2) 点「切换租户」打开列表（只读，不选任何租户）
        switched = False
        for factory in (
            lambda: page.get_by_role("menuitem", name="切换租户", exact=True).last,
            lambda: page.get_by_text("切换租户", exact=True).last,
        ):
            try:
                loc = factory()
                if loc.count() and loc.is_visible(timeout=2500):
                    loc.click()
                    page.wait_for_timeout(3000)
                    switched = True
                    break
            except Exception:
                continue
        r["switch_clicked"] = switched
        r["steps"]["switch_list"] = snap(page, "switch-list")
        print("  switch clicked:", switched, flush=True)
        s = r["steps"]["switch_list"]
        print("  has创建租户:", s["has_create_tenant"], "| has客商:", s["has_keshang"],
              "| has认证:", s["has_cert"], "| has申请中:", s["has_applying"], flush=True)

        # 3) 若列表里有「创建租户」，点开看弹窗结构（不提交）
        if s["has_create_tenant"]:
            try:
                loc = page.get_by_text("创建租户", exact=True).last
                if loc.count() and loc.is_visible(timeout=2500):
                    loc.click()
                    page.wait_for_timeout(3500)
                    r["steps"]["create_dialog"] = snap(page, "create-dialog")
                    d = r["steps"]["create_dialog"]
                    print("  create dialog has客商:", d["has_keshang"], flush=True)
            except Exception as exc:  # noqa: BLE001
                r["create_dialog_error"] = str(exc)[:200]

        # 4) 关闭弹窗，回到工作台看左侧菜单（客商是否改动了租户维度菜单）
        for _ in range(3):
            page.keyboard.press("Escape")
            page.wait_for_timeout(700)
        r["steps"]["after_escape"] = snap(page, "after-escape")

        ctx.close()
        b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWROTE {OUT}", flush=True)


if __name__ == "__main__":
    main()
