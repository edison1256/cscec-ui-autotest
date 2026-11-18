"""诊断：服务中心资源卡片的 DOM 结构（只读，不点击）。

前几轮失败原因：
  - 「立即申请」在 DOM 里但不可见（hover 浮层）
  - 用 getBoundingClientRect 找「尺寸最大的祖先」会匹配到整片网格
  - 按文字找标题时误matched 到筛选标签（换个天赋/itsm服务...），把列表过滤了

本脚本只做两件事：
  1. 打印页面上出现频率最高的 class 名（定位卡片容器）
  2. 打印每个候选卡片容器的 tag/class/rect/内部文字片段

不点击任何元素。
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.login_page import LoginPage  # noqa: E402

OUT = Path("reports/service_center/_dom_diag.json")


def click_text(page, label: str, wait: int = 3500) -> bool:
    for factory in (
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
            page.wait_for_timeout(2500)
            for _ in range(2):
                page.keyboard.press("Escape")
                page.wait_for_timeout(400)

            info = page.evaluate(
                "() => { const s = localStorage.getItem('__login_info__');"
                " return s ? JSON.parse(s) : null; }"
            )
            r["identity"] = {k: (info or {}).get(k) for k in ("orgName", "orgNo", "userName")}

            click_text(page, "服务中心", 5000)
            r["url"] = page.url[:160]

            # 1) class 频率
            r["class_freq"] = page.evaluate(
                """() => {
                     const m = {};
                     document.querySelectorAll('[class]').forEach(e => {
                       (e.className && typeof e.className === 'string' ? e.className : '')
                         .split(/\\s+/).filter(Boolean)
                         .forEach(c => { m[c] = (m[c] || 0) + 1; });
                     });
                     return Object.entries(m).sort((a,b) => b[1]-a[1]).slice(0, 25);
                   }"""
            )

            # 2) 候选卡片：含「立即申请」的最近"合适尺寸"祖先，逐个列出
            r["cards"] = page.evaluate(
                """() => {
                     const spans = Array.from(document.querySelectorAll('*'))
                       .filter(e => e.children.length === 0
                                    && (e.innerText||'').trim() === '立即申请');
                     return spans.slice(0, 6).map(sp => {
                       let p = sp.parentElement;
                       for (let k = 0; k < 8 && p; k++, p = p.parentElement) {
                         const r = p.getBoundingClientRect();
                         if (r.width >= 180 && r.width <= 420 && r.height >= 120 && r.height <= 380) {
                           return {
                             tag: p.tagName,
                             cls: (p.className && typeof p.className === 'string') ? p.className.slice(0, 80) : '',
                             rect: {x: Math.round(r.x), y: Math.round(r.y),
                                    w: Math.round(r.width), h: Math.round(r.height)},
                             text: (p.innerText || '').trim().slice(0, 90),
                           };
                         }
                       }
                       const pr = sp.parentElement ? sp.parentElement.getBoundingClientRect() : null;
                       return {tag: 'NONE', cls: '', rect: pr ? {x: Math.round(pr.x), y: Math.round(pr.y),
                               w: Math.round(pr.width), h: Math.round(pr.height)} : null,
                               text: (sp.parentElement ? sp.parentElement.innerText : '').slice(0, 60)};
                     });
                   }"""
            )

            # 3) 所有 a[href]（若卡片是链接）
            r["anchors"] = page.evaluate(
                """() => Array.from(document.querySelectorAll('a[href]'))
                     .map(a => ({href: a.getAttribute('href'), text: (a.innerText||'').trim().slice(0,40)}))
                     .filter(o => o.href && !o.href.startsWith('javascript'))
                     .slice(0, 20)"""
            )

            page.screenshot(path=str(OUT.parent / "_diag-service-center.png"), full_page=True)
        except Exception as exc:  # noqa: BLE001
            r["error"] = f"{type(exc).__name__}: {exc}"[:200]
        finally:
            ctx.close()
            b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

    print("身份:", json.dumps(r.get("identity"), ensure_ascii=False))
    print("URL:", (r.get("url") or "")[:100])
    print("\n=== class 频率 top15 ===")
    for c, n in (r.get("class_freq") or [])[:15]:
        print(f"  {c[:46]:46} {n}")
    print("\n=== 候选卡片 ===")
    for c in (r.get("cards") or []):
        print(f"  {c.get('tag')} .{(c.get('cls') or '')[:40]}")
        print(f"    rect={c.get('rect')}  text={(c.get('text') or '')[:60]}")
    print("\n=== anchors ===")
    for a in (r.get("anchors") or [])[:12]:
        print(f"  {a['href'][:70]}  |  {a['text'][:30]}")
    print(f"\nWROTE {OUT}")


if __name__ == "__main__":
    main()
