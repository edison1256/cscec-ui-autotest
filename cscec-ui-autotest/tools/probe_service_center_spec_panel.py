"""探测：点「立即申请」之后展开的「资源规格」列表结构（只读，不用 force）。

用户 2026-11-18 纠正的完整交互链：
  1. hover 卡片 → 出现「立即申请」链接
  2. 点「立即申请」→ **上方展开可用资源规格**（如「资源申请」）
  3. 点某个规格 → 进入订阅页
  4. **进订阅页时才出现「切换其他租户」提示**

上一轮我只做到第 2 步就判定"无提示"，且用了 force=True（违反黑盒原则）。
本轮只做一件事：把第 2 步点开，把新增出来的规格项结构抓清楚。
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.login_page import LoginPage  # noqa: E402

OUT = Path("reports/service_center/_spec_panel.json")
SHOT = Path("reports/service_center")


def snap(page, tag: str) -> None:
    try:
        SHOT.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOT / f"_spec-{tag}.png"), full_page=True)
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


def main() -> None:
    if settings.ENV != "uat":
        raise SystemExit("必须 ENV=uat")

    r: dict = {"checked_at": datetime.now().isoformat(timespec="seconds")}

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
                page.wait_for_timeout(400)

            # 确保个人工作台身份
            info = login_info(page)
            r["identity"] = {k: info.get(k) for k in ("orgName", "orgNo", "userName")}
            if "个人工作台" not in (info.get("orgName") or ""):
                name = info.get("userName")
                loc = page.get_by_text(name, exact=True).first
                if loc.count():
                    loc.hover()
                    page.wait_for_timeout(2200)
                sw = page.get_by_text("切换租户", exact=True).last
                if sw.count():
                    sw.click()
                    page.wait_for_timeout(2500)
                    tgt = page.get_by_text("个人工作台", exact=True)
                    if tgt.count():
                        tgt.last.click()
                        page.wait_for_timeout(4000)
            r["identity_after"] = {
                k: login_info(page).get(k) for k in ("orgName", "orgNo")
            }

            # 进服务中心
            for factory in (
                lambda: page.get_by_role("link", name="服务中心", exact=True).last,
                lambda: page.get_by_text("服务中心", exact=True).last,
            ):
                try:
                    loc = factory()
                    if loc.count() and loc.is_visible(timeout=2000):
                        loc.click()
                        page.wait_for_timeout(4500)
                        break
                except Exception:
                    continue

            cards = page.locator("div[class*='publishItem']")
            r["card_count"] = cards.count()
            card = cards.first
            r["card_title"] = (card.inner_text() or "").splitlines()[0][:40]

            # hover → 点「立即申请」（普通 click，不用 force）
            card.hover(timeout=8000)
            page.wait_for_timeout(1200)
            btn = card.get_by_text("立即申请", exact=True)
            r["btn_visible"] = btn.count() > 0 and btn.first.is_visible()
            snap(page, "01-hover")

            before_text = page.locator("body").inner_text()
            before_html_len = page.evaluate("() => document.body.innerHTML.length")

            btn.first.click(timeout=8000)
            page.wait_for_timeout(3500)
            snap(page, "02-after-apply")

            after_text = page.locator("body").inner_text()
            after_html_len = page.evaluate("() => document.body.innerHTML.length")
            r["html_len_delta"] = after_html_len - before_html_len
            r["url_after"] = page.url[:180]

            # 新增的文本行（规格项通常出现在这里）
            before_set = set(x.strip() for x in before_text.splitlines() if x.strip())
            after_lines = [x.strip() for x in after_text.splitlines() if x.strip()]
            new_lines = [x for x in after_lines if x not in before_set]
            r["new_lines"] = new_lines[:40]

            # 规格候选：短文本 + 在卡片附近 + 可点
            r["spec_candidates"] = page.evaluate(
                """() => {
                     const out = [];
                     document.querySelectorAll('*').forEach(e => {
                       if (e.children.length !== 0) return;
                       const t = (e.innerText || '').trim();
                       if (!t || t.length < 2 || t.length > 20) return;
                       const r = e.getBoundingClientRect();
                       if (r.width <= 0 || r.height <= 0) return;
                       if (r.y < 60 || r.y > 700) return;
                       out.push({t, x: Math.round(r.x), y: Math.round(r.y),
                                 w: Math.round(r.width), h: Math.round(r.height),
                                 cls: (e.className && typeof e.className === 'string') ? e.className.slice(0,40) : ''});
                     });
                     return out.slice(0, 50);
                   }"""
            )

            # 所有可见的 popover/dropdown 容器
            r["panels"] = page.evaluate(
                """() => {
                     const sels = ['.ant-popover-inner-content', '.ant-dropdown-menu',
                                   '[class*="popover"]', '[class*="dropdown"]',
                                   '[class*="spec"]', '[class*="Spec"]'];
                     const seen = new Set(), out = [];
                     sels.forEach(s => {
                       document.querySelectorAll(s).forEach(e => {
                         if (seen.has(e)) return;
                         seen.add(e);
                         const r = e.getBoundingClientRect();
                         if (r.width <= 0 || r.height <= 0) return;
                         out.push({cls: (e.className||'').toString().slice(0,60),
                                   rect: {x: Math.round(r.x), y: Math.round(r.y),
                                          w: Math.round(r.width), h: Math.round(r.height)},
                                   text: (e.innerText||'').trim().slice(0, 160)});
                       });
                     });
                     return out.slice(0, 10);
                   }"""
            )

        except Exception as exc:  # noqa: BLE001
            r["error"] = f"{type(exc).__name__}: {exc}"[:250]
            snap(page, "99-failed")
        finally:
            ctx.close()
            b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

    print("身份:", json.dumps(r.get("identity_after") or r.get("identity"), ensure_ascii=False))
    print("卡片:", r.get("card_count"), "|", r.get("card_title"))
    print("「立即申请」可见:", r.get("btn_visible"))
    print("点击后 URL:", (r.get("url_after") or "")[:110])
    print("HTML 长度变化:", r.get("html_len_delta"))
    print("\n=== 新增文本行 ===")
    for t in (r.get("new_lines") or [])[:25]:
        print("  +", t[:60])
    print("\n=== 面板容器 ===")
    for pn in (r.get("panels") or []):
        print(f"  .{pn['cls'][:40]} rect={pn['rect']}")
        print(f"    text={pn['text'][:120]}")
    print(f"\nWROTE {OUT}")


if __name__ == "__main__":
    main()
