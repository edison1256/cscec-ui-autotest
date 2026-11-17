"""探测生产控制台「权限管理 → 客商管理」各子菜单的实际状态（只读）。

背景：
  我此前记录「生产控制台没有客商管理菜单」是错的 —— 它是「权限管理」下的
  子菜单，我没展开一级菜单就下了结论（用户 2026-11-17 指正并给出截图）。
  截图显示子项：认证审核 / 用户中心 / 企业名录 / 客商列表 / 入驻配置 /
  企业类型管理 / 认证材料库（可能还有更多，需滚动）。

本轮目标：
  逐个点子菜单，记录 URL、页面关键文案、列表接口与数据量，
  作为只读用例的输入。同时确认「交互是否已简化」，避免按大纲理想态写断言。

控制台允许直接访问 irp 根域名（用户 2026-11-17 明确）；进入后一律点菜单。
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.login_page import LoginPage  # noqa: E402

OUT = Path("reports/keshang/_console_keshang_recon.json")
SHOT = Path("reports/keshang")

SUBMENUS = [
    "认证审核",
    "用户中心",
    "企业名录",
    "客商列表",
    "入驻配置",
    "企业类型管理",
    "认证材料库",
]


def snap(page, tag: str) -> None:
    try:
        SHOT.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(SHOT / f"_ks-{tag}.png"), full_page=True)
    except Exception:
        pass


def text_of(page, n: int = 2500) -> str:
    try:
        return page.locator("body").inner_text()[:n]
    except Exception:
        return ""


def click_text(page, label: str, wait: int = 3000) -> bool:
    for factory in (
        lambda: page.get_by_role("menuitem", name=label, exact=True).last,
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
    if settings.ENV != "prod":
        raise SystemExit("必须 ENV=prod")

    r = {"checked_at": datetime.now().isoformat(timespec="seconds"), "menus": {}}
    bucket: list[dict] = []

    def on_resp(resp):
        if "/irp-api/" not in resp.url:
            return
        item = {"url": resp.url[:190], "method": resp.request.method, "status": resp.status}
        try:
            body = resp.json()
        except Exception:
            return
        data = body.get("data") if isinstance(body, dict) else None
        if isinstance(data, dict):
            rows = data.get("list") or data.get("records") or data.get("rows")
            if isinstance(rows, list):
                item["total"] = data.get("total")
                item["len"] = len(rows)
                if rows and isinstance(rows[0], dict):
                    item["fields"] = list(rows[0].keys())[:22]
                bucket.append(item)
        elif isinstance(data, list):
            item["len"] = len(data)
            bucket.append(item)

    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel=settings.BROWSER_CHANNEL)
        except Exception:
            b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1680, "height": 1100}, ignore_https_errors=True)
        page = ctx.new_page()
        page.set_default_timeout(25000)
        page.on("response", on_resp)

        try:
            # 控制台：允许直连 irp 根域名（用户许可），进入后点菜单
            LoginPage(page).login()
            page.wait_for_timeout(3500)
            r["console_url"] = page.url[:180]
            try:
                info = page.evaluate(
                    "() => { const s = localStorage.getItem('__login_info__');"
                    " return s ? JSON.parse(s) : null; }"
                )
            except Exception:
                info = None
            r["login_info"] = {
                k: (info or {}).get(k)
                for k in ("userNo", "userName", "orgNo", "orgName", "tenantNo")
            }
            print("身份:", json.dumps(r["login_info"], ensure_ascii=False))

            # 展开「权限管理」
            r["perm_clicked"] = click_text(page, "权限管理", 2500)
            body = text_of(page)
            r["perm_submenu"] = [
                x.strip() for x in body.splitlines()
                if x.strip() in ("登录管理", "用户管理", "租户管理", "角色管理", "客商管理")
            ]
            print("权限管理子项:", r["perm_submenu"])

            # 点「客商管理」展开
            r["keshang_clicked"] = click_text(page, "客商管理", 3000)
            body = text_of(page)
            found = [x.strip() for x in body.splitlines() if x.strip() in SUBMENUS]
            r["keshang_submenu_found"] = found
            print("客商管理子项(实测):", found)
            snap(page, "01-keshang-expanded")

            # 逐个点子菜单
            for label in found:
                bucket.clear()
                entry: dict = {}
                try:
                    if click_text(page, label, 5000):
                        page.wait_for_timeout(2500)
                        entry["url"] = page.url[:190]
                        txt = text_of(page, 2000)
                        entry["text_head"] = txt[:700]
                        entry["apis"] = bucket[:4]
                    else:
                        entry["error"] = "点击失败"
                except Exception as exc:  # noqa: BLE001
                    entry["error"] = f"{type(exc).__name__}: {exc}"[:150]
                r["menus"][label] = entry
                snap(page, f"02-{label}")
                apis = entry.get("apis") or []
                print(f"\n[{label}] url={(entry.get('url') or '')[:100]}")
                for a in apis:
                    print(f"   {a['method']} {a['url'][:100]} total={a.get('total')} len={a.get('len')}")
                    print(f"     fields={(a.get('fields') or [])[:14]}")

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
