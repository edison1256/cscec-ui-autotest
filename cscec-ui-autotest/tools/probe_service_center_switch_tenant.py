"""UAT 实测：服务中心发起申请时，个人工作台身份是否提示「切换其他租户」。

需求（2026-11-18 用户）：
  门户【服务中心】发起任何资源时，若订阅用户当前为【个人工作台】，
  点击「发起申请」需提醒【切换其他租户】。

本脚本只做探测：
  1. 记录当前登录身份（orgName / tenantNo / orgNo）
  2. 进服务中心，列出可见资源
  3. 点一个资源的「发起申请」，抓弹窗/提示文本
  4. 判断是否含「切换其他租户」类提示

刻意不填表、不提交 —— 「发起申请」若只是弹提醒，不会产生数据。
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.login_page import LoginPage  # noqa: E402

OUT = Path("reports/service_center/_probe_switch_tenant_prompt.json")
SHOT = Path("reports/service_center")

# 可能的提醒文案（模糊匹配用）
PROMPT_HINTS = ("切换其他租户", "切换租户", "其他租户", "个人工作台", "当前租户", "无权限", "请切换")


def snap(page, tag: str) -> None:
    try:
        SHOT.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOT / f"_sc-{tag}.png"), full_page=True)
    except Exception:
        pass


def login_info(page) -> dict:
    try:
        v = page.evaluate(
            "() => { const s = localStorage.getItem('__login_info__');"
            " return s ? JSON.parse(s) : null; }"
        )
    except Exception:
        return {}
    return v if isinstance(v, dict) else {}


def body_text(page, n: int = 3000) -> str:
    try:
        return page.locator("body").inner_text()[:n]
    except Exception:
        return ""


def click_text(page, label: str, wait: int = 3000) -> bool:
    for factory in (
        lambda: page.get_by_role("menuitem", name=label, exact=True).last,
        lambda: page.get_by_role("link", name=label, exact=True).last,
        lambda: page.get_by_text(label, exact=True).last,
    ):
        try:
            loc = factory()
            if loc.count() and loc.is_visible(timeout=2000):
                loc.click()
                page.wait_for_timeout(wait)
                return True
        except Exception:
            continue
    return False


def visible_dialogs(page) -> list[str]:
    """抓所有可见的弹窗/提示容器文本。"""
    out = []
    for sel in (
        ".ant-modal-content",
        ".ant-message-notice-content",
        "[role='dialog']",
        ".ant-popover-inner-content",
        ".ant-notification-notice",
    ):
        try:
            loc = page.locator(sel)
            for i in range(min(loc.count(), 4)):
                el = loc.nth(i)
                if el.is_visible():
                    t = (el.inner_text() or "").strip()
                    if t:
                        out.append(f"{sel}: {t[:300]}")
        except Exception:
            continue
    return out


def main() -> None:
    if settings.ENV != "uat":
        raise SystemExit("必须 ENV=uat")

    r = {"checked_at": datetime.now().isoformat(timespec="seconds"), "env": settings.ENV}

    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel=settings.BROWSER_CHANNEL)
        except Exception:
            b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1680, "height": 1100}, ignore_https_errors=True)
        page = ctx.new_page()
        page.set_default_timeout(25000)

        try:
            LoginPage(page).login_portal()
            page.wait_for_timeout(3000)
            for _ in range(2):
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)

            info = login_info(page)
            r["identity"] = {
                k: info.get(k) for k in ("userNo", "userName", "orgNo", "orgName", "tenantNo", "tenantName")
            }
            r["portal_url"] = page.url[:180]
            print("身份:", json.dumps(r["identity"], ensure_ascii=False))
            print("门户:", r["portal_url"][:110])

            # 需求前提：订阅用户当前为「个人工作台」。
            # 若当前不是，先走 显示名 → 切换租户 切过去。
            name = r["identity"].get("userName")
            if name and "个人工作台" not in (r["identity"].get("orgName") or ""):
                loc = page.get_by_text(name, exact=True).first
                if loc.count():
                    loc.hover()
                    page.wait_for_timeout(2400)
                # 先看切换租户面板里有哪几个租户
                sw = page.get_by_text("切换租户", exact=True).last
                if sw.count():
                    sw.click()
                    page.wait_for_timeout(3000)
                    panel = body_text(page, 2500)
                    r["tenant_panel"] = [
                        x.strip() for x in panel.splitlines()
                        if x.strip().endswith(("租户", "空间", "工作台")) or "工作台" in x
                    ][:15]
                    snap(page, "00-tenant-panel")
                    # 优先点「个人工作台」
                    picked = None
                    for lb in ("个人工作台",):
                        pc = page.get_by_text(lb, exact=True)
                        if pc.count():
                            try:
                                pc.last.click()
                                page.wait_for_timeout(5000)
                                picked = lb
                            except Exception as exc:  # noqa: BLE001
                                r["error_pick"] = str(exc)[:120]
                            break
                    r["switched_to"] = picked
                    page.wait_for_timeout(2500)
                    r["identity_after_switch"] = {
                        k: login_info(page).get(k) for k in ("orgNo", "orgName", "tenantNo")
                    }
                    print("切换租户面板:", r.get("tenant_panel"))
                    print("切换到:", picked, "->", json.dumps(r["identity_after_switch"], ensure_ascii=False))

            # 进服务中心
            r["service_center_clicked"] = click_text(page, "服务中心", 4000)
            r["sc_url"] = page.url[:180]
            txt = body_text(page, 2500)
            r["sc_text"] = txt[:1500]
            snap(page, "01-service-center")
            print("服务中心:", r["service_center_clicked"], "->", r["sc_url"][:110])

            # 卡片容器实测为 div[class*='publishItem']（240×284）。
            # class 带 hash 后缀会变，所以用属性包含匹配。
            page.wait_for_timeout(1200)
            cards = page.locator("div[class*='publishItem']")
            n_cards = cards.count()
            r["card_count"] = n_cards
            print("卡片数量:", n_cards)

            opened = False
            first_title = ""
            if n_cards:
                try:
                    first_title = (cards.first.inner_text() or "").splitlines()[0][:40]
                    cards.first.click(timeout=10000)
                    page.wait_for_timeout(4500)
                    opened = page.url != r["sc_url"]
                    r["card_title"] = first_title
                except Exception as exc:  # noqa: BLE001
                    r["error_card_click"] = str(exc)[:180]
                    print("  点卡片失败:", str(exc)[:110])

            r["detail_opened"] = opened
            r["url_after_card"] = page.url[:220]
            r["text_after_card"] = body_text(page, 1500)
            snap(page, "02-card-detail")
            print("点卡片:", opened, "| 标题:", first_title, "->", r["url_after_card"][:110])

            # 「立即申请」默认 display:none，必须 hover 卡片让它浮现。
            # force=True 点隐藏元素不会触发业务逻辑（上轮实测 URL/页面全无变化）。
            clicked = None
            if n_cards:
                card = cards.first
                try:
                    card.hover(timeout=8000)
                    page.wait_for_timeout(1200)
                    snap(page, "03-card-hover")
                    btn = card.get_by_text("立即申请", exact=True)
                    vis = btn.count() > 0 and btn.first.is_visible()
                    r["apply_btn_visible_after_hover"] = vis
                    print("hover 后「立即申请」可见:", vis)
                    if vis:
                        # 点击可能新开标签页（工作台那次的同款坑），必须检测
                        pages_before = len(ctx.pages)
                        btn.first.click(timeout=8000)
                        page.wait_for_timeout(4500)
                        clicked = "立即申请(hover后点击)"
                        r["pages_delta"] = len(ctx.pages) - pages_before
                        if len(ctx.pages) > pages_before:
                            target = ctx.pages[-1]
                            try:
                                target.wait_for_load_state("domcontentloaded", timeout=20000)
                            except Exception:
                                pass
                            target.wait_for_timeout(2500)
                            r["new_tab_url"] = target.url[:220]
                            r["new_tab_dialogs"] = visible_dialogs(target)
                            try:
                                r["new_tab_text"] = target.locator("body").inner_text()[:1500]
                            except Exception:
                                r["new_tab_text"] = ""
                            snap(target, "04-new-tab")
                            blob2 = " ".join(r["new_tab_dialogs"]) + " " + r["new_tab_text"]
                            r["new_tab_prompt_hits"] = [w for w in PROMPT_HINTS if w in blob2]
                            r["new_tab_has_switch_prompt"] = any(
                                w in blob2 for w in ("切换其他租户", "切换租户")
                            )
                            print("新标签页:", r["new_tab_url"][:110])
                            print("新页弹窗:", json.dumps(r["new_tab_dialogs"], ensure_ascii=False)[:300])
                            print("新页是否提示切换租户:", r["new_tab_has_switch_prompt"])
                except Exception as exc:  # noqa: BLE001
                    r["error_hover_click"] = str(exc)[:180]
                    print("  hover/点击失败:", str(exc)[:110])

            r["entry_clicked"] = clicked
            print("点击申请入口:", clicked)

            r["url_after_click"] = page.url[:180]
            r["dialogs"] = visible_dialogs(page)
            r["body_after_click"] = body_text(page, 1500)
            snap(page, "02-after-click")

            # 判断是否命中「切换其他租户」类提示
            blob = " ".join(r["dialogs"]) + " " + r["body_after_click"]
            r["prompt_hits"] = [w for w in PROMPT_HINTS if w in blob]
            r["has_switch_tenant_prompt"] = any(
                w in blob for w in ("切换其他租户", "切换租户")
            )
            print("\n弹窗:", json.dumps(r["dialogs"], ensure_ascii=False)[:600])
            print("命中提示词:", r["prompt_hits"])
            print("是否提示切换租户:", r["has_switch_tenant_prompt"])

        except Exception as exc:  # noqa: BLE001
            r["error"] = f"{type(exc).__name__}: {exc}"[:300]
            r["url_at_failure"] = page.url[:180]
            snap(page, "99-failed")
            print("!! 异常:", r["error"])
        finally:
            ctx.close()
            b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWROTE {OUT}")


if __name__ == "__main__":
    main()
