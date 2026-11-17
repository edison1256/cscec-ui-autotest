"""黑盒对照：从门户切换租户进入空间，验证租户标识与列表数据范围。

质疑（2026-11-17 用户）：
  `ZH_01_0000` 是**根节点**（中建云），按设计不应存在用户；
  用户只归属于根节点下两个空间：
      中建云工作台空间  ZH_01_0000_0000
      中建云控制台空间  ZH_01_0000_000C
  若走真实鼠标点击，租户不应显示为中建云，数据也不该有那么多。

自查动机：此前的探针用 `goto(...#/portal/home/workbench?suitKey=portal)` 直链，
可能绕过了视图/空间选择，进到该账号本不该有的套件 —— 那样看到的"全量数据"
是直链视图的产物，不是真实业务视图。

做法（全程点击，只有登录和门户首页用 goto）：
  1. 登录门户 cloud 域
  2. hover 右上角显示名 → 读个人卡片（当前租户/空间）
  3. 点「切换租户」→ 列出可选空间
  4. 点「中建云控制台空间」→ 进入
  5. 读 __login_info__ 看 tenantNo 是否变成 ..._000C
  6. 从工作台点「被订阅的订单」→ 抓接口与归属分布
  7. 对照组：再用旧直链进 suitKey=portal，抓同样数据，对比差异

只读。
"""

import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.login_page import LoginPage  # noqa: E402

OUT = Path("reports/coverage-gaps/_blackbox_vs_deeplink.json")

SPACES = ("中建云控制台空间", "中建云工作台空间")


def snap(page, tag: str) -> None:
    try:
        p = Path("reports/coverage-gaps")
        p.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(p / f"_bb-{tag}.png"), full_page=True)
    except Exception:
        pass


def login_info(page) -> dict:
    try:
        info = page.evaluate(
            "() => { const s = localStorage.getItem('__login_info__');"
            " return s ? JSON.parse(s) : null; }"
        )
    except Exception:
        return {}
    return info if isinstance(info, dict) else {}


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


def collect_scope(page, label: str, api_hint: str, wait_s: int = 12) -> dict:
    """点 label 后捕获匹配 api_hint 的列表响应，统计归属分布。"""
    captured: dict = {}

    def on_resp(resp):
        if api_hint.lower() not in resp.url.lower():
            return
        captured["response"] = resp

    page.on("response", on_resp)
    try:
        click_text(page, label, 3000)
        waited = 0
        while "response" not in captured and waited < wait_s * 2:
            page.wait_for_timeout(500)
            waited += 1
    finally:
        page.remove_listener("response", on_resp)

    resp = captured.get("response")
    if resp is None:
        return {"error": f"未捕获 {api_hint}"}
    out = {"url": resp.url[:200], "status": resp.status}
    try:
        body = resp.json()
        data = body.get("data") if isinstance(body, dict) else None
        if isinstance(data, dict):
            rows = data.get("list") or data.get("records") or data.get("rows")
            out["total"] = data.get("total")
            if isinstance(rows, list):
                out["list_len"] = len(rows)
                dist = {}
                for f in ("tenantNo", "tenantName", "creator", "userName"):
                    vals = [str(r.get(f)) for r in rows if isinstance(r, dict) and r.get(f) is not None]
                    if vals:
                        c = Counter(vals)
                        dist[f] = {"unique": len(c), "top": c.most_common(4)}
                out["dist"] = dist
    except Exception as exc:  # noqa: BLE001
        out["parse_error"] = str(exc)[:120]
    return out


def main() -> None:
    if settings.ENV != "prod":
        raise SystemExit("必须 ENV=prod")

    r = {"checked_at": datetime.now().isoformat(timespec="seconds")}

    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel=settings.BROWSER_CHANNEL)
        except Exception:
            b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1680, "height": 1100}, ignore_https_errors=True)
        page = ctx.new_page()
        page.set_default_timeout(25000)

        try:
            # ---- 1. 门户登录（点击进入，只有这里用 goto 进站点） ----
            LoginPage(page).login_portal()
            page.wait_for_timeout(3000)
            for _ in range(2):
                page.keyboard.press("Escape")
                page.wait_for_timeout(500)
            r["portal_url"] = page.url[:180]
            r["info_at_portal"] = login_info(page)
            snap(page, "01-portal")

            # ---- 2. hover 显示名，读个人卡片 ----
            name = (r["info_at_portal"] or {}).get("userName")
            if name:
                loc = page.get_by_text(name, exact=True).first
                if loc.count():
                    loc.hover()
                    page.wait_for_timeout(2500)
            try:
                card = page.locator("body").inner_text()[:1500]
            except Exception:
                card = ""
            r["card_text"] = card
            snap(page, "02-card")

            # ---- 3. 切换租户，列空间 ----
            r["switcher_opened"] = click_text(page, "切换租户", 3500)
            try:
                sw = page.locator("body").inner_text()[:2500]
            except Exception:
                sw = ""
            r["switcher_text"] = sw
            r["spaces_found"] = [s for s in SPACES if s in sw]
            snap(page, "03-switcher")

            # ---- 4. 进入控制台空间（点击） ----
            entered = False
            for space in ("中建云控制台空间",):
                if click_text(page, space, 6000):
                    entered = True
                    break
            r["space_entered"] = entered
            page.wait_for_timeout(3000)
            r["url_after_enter"] = page.url[:200]
            r["info_after_enter"] = login_info(page)
            try:
                r["text_after_enter"] = page.locator("body").inner_text()[:1200]
            except Exception:
                r["text_after_enter"] = ""
            snap(page, "04-after-enter")

            # ---- 5. 从工作台点「被订阅的订单」（黑盒） ----
            r["blackbox_subscribed"] = collect_scope(
                page, "被订阅的订单", "workbench/rsc/app/apply/history/list"
            )
            snap(page, "05-blackbox-subscribed")

            # ---- 6. 对照组：旧直链 suitKey=portal ----
            page.goto(
                "https://irp.cscec.com/udpweb/portal/index.html"
                "#/portal/home/workbench?suitKey=portal",
                wait_until="domcontentloaded",
                timeout=settings.NAVIGATION_TIMEOUT,
            )
            page.wait_for_timeout(5000)
            r["url_deeplink"] = page.url[:200]
            r["info_after_deeplink"] = login_info(page)
            r["deeplink_subscribed"] = collect_scope(
                page, "被订阅的订单", "workbench/rsc/app/apply/history/list"
            )
            snap(page, "06-deeplink")

        except Exception as exc:  # noqa: BLE001
            r["error"] = f"{type(exc).__name__}: {exc}"[:300]
            r["url_at_failure"] = page.url[:200]
            snap(page, "99-failed")
        finally:
            ctx.close()
            b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")

    print("=== 门户 ===")
    print(" info:", json.dumps(r.get("info_at_portal"), ensure_ascii=False))
    print("=== 切换租户 ===")
    print(" spaces_found:", r.get("spaces_found"))
    print("=== 进入空间后 ===")
    print(" entered:", r.get("space_entered"), "url:", (r.get("url_after_enter") or "")[:110])
    print(" info:", json.dumps(r.get("info_after_enter"), ensure_ascii=False))
    for key in ("blackbox_subscribed", "deeplink_subscribed"):
        v = r.get(key) or {}
        print(f"\n=== {key} ===")
        print(" url:", (v.get("url") or "")[:120], v.get("error") or "")
        print(" total=", v.get("total"), "len=", v.get("list_len"))
        for f, d in (v.get("dist") or {}).items():
            print(f"  {f}: unique={d['unique']} top={d['top'][:3]}")
    print("\n deeplink info:", json.dumps(r.get("info_after_deeplink"), ensure_ascii=False))
    print(f"\nWROTE {OUT}")


if __name__ == "__main__":
    main()
