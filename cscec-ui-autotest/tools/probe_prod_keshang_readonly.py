"""生产环境客商功能可见性只读探测。

严格边界：
  - 只做导航（点菜单/tab）与读取文本，**不点任何提交/保存/删除/审核按钮**
  - 不输入查询条件、不修改任何业务对象
  - 每个页面截图留证

目的：确认客商需求上线后，生产环境里
  1) 控制台是否有「客商管理」入口，位置在哪
  2) 权限管理下是否有客商相关子菜单（组织树/租户/成员）
  3) 工作台个人卡片与租户切换是否有客商相关展示（企业认证状态等）
为「生产回归测试范围」提供事实依据，不在此脚本里做断言。
"""

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.login_page import LoginPage  # noqa: E402

OUT = Path("reports/prod-keshang/_probe.json")
SHOT = Path("reports/prod-keshang")

# 只允许点击这些「导航类」文本，其余一律不点
NAV_WHITELIST = {
    "客商管理",
    "权限管理",
    "组织管理",
    "租户管理",
    "成员管理",
    "登录管理",
    "资源管理",
    "订阅服务",
    "运营管理",
    "系统配置",
    "计量统计",
    "工作台",
    "应用中心",
}

# 命中这些词说明页面是「危险操作页」，只读不点
DANGER_HINTS = ("删除", "移除", "审核", "通过", "驳回", "提交", "保存", "新建", "添加")


def safe_name(s: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fa5\-]", "_", s)[:30]


def body_text(page) -> str:
    try:
        return page.locator("body").inner_text()
    except Exception:
        return ""


def dump_nav(page) -> dict:
    info = {}
    try:
        info["url"] = page.url
        txt = body_text(page)
        info["body_head"] = txt[:900]
        # 菜单候选：短文本且不以数字开头
        lines = [x.strip() for x in txt.splitlines() if x.strip()]
        info["short_lines"] = [x for x in lines if 2 <= len(x) <= 8][:80]
    except Exception as exc:  # noqa: BLE001
        info["error"] = str(exc)[:200]
    return info


def click_nav(page, label: str) -> bool:
    """只点白名单里的导航项；点完等渲染。"""
    if label not in NAV_WHITELIST:
        return False
    for factory in (
        lambda: page.get_by_role("menuitem", name=label, exact=True).last,
        lambda: page.get_by_text(label, exact=True).last,
    ):
        try:
            loc = factory()
            if loc.count() and loc.is_visible(timeout=2500):
                loc.click()
                page.wait_for_timeout(3500)
                return True
        except Exception:
            continue
    return False


def scan_prod(page, tag: str) -> dict:
    info = dump_nav(page)
    txt = info.get("body_head", "")
    info["has_keshang"] = "客商" in body_text(page)
    info["danger_words"] = [w for w in DANGER_HINTS if w in txt]
    try:
        page.screenshot(path=str(SHOT / f"_prod-{tag}.png"), full_page=True)
    except Exception:
        pass
    return info


def main() -> None:
    if settings.ENV != "prod":
        raise SystemExit("必须用 ENV=prod 运行：这是生产只读探测")

    SHOT.mkdir(parents=True, exist_ok=True)
    r = {"env": settings.ENV, "user_masked": settings.USERNAME[:3] + "***", "pages": {}}

    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel=settings.BROWSER_CHANNEL)
        except Exception:
            b = p.chromium.launch(headless=True)
        ctx = b.new_context(viewport={"width": 1680, "height": 1050})
        page = ctx.new_page()
        page.set_default_timeout(25000)

        # 控制台域登录
        LoginPage(page).login()
        page.wait_for_timeout(3000)
        r["console_landing"] = page.url[:160]
        r["pages"]["console-home"] = scan_prod(page, "console-home")
        print("console landing:", page.url[:120], flush=True)
        print("  has客商:", r["pages"]["console-home"]["has_keshang"], flush=True)

        # 逐个点导航，找客商入口
        found = {}
        for label in (
            "权限管理",
            "租户管理",
            "组织管理",
            "成员管理",
            "登录管理",
            "客商管理",
            "系统配置",
            "运营管理",
        ):
            if click_nav(page, label):
                info = scan_prod(page, f"nav-{label}")
                found[label] = {
                    "url": info.get("url", "")[:160],
                    "has_keshang": info["has_keshang"],
                    "short_lines": info.get("short_lines", [])[:40],
                    "danger_words": info["danger_words"],
                }
                print(
                    f"  [{label}] url={info.get('url','')[:90]} has客商={info['has_keshang']}",
                    flush=True,
                )
        r["console_nav"] = found

        # 门户域单独登录
        ctx2 = b.new_context(viewport={"width": 1680, "height": 1050})
        p2 = ctx2.new_page()
        p2.set_default_timeout(25000)
        try:
            LoginPage(p2).login_portal()
            p2.wait_for_timeout(3000)
            r["portal_landing"] = p2.url[:160]
            info = scan_prod(p2, "portal-home")
            r["pages"]["portal-home"] = info
            print("portal landing:", p2.url[:120], flush=True)
            print("  has客商:", info["has_keshang"], flush=True)
            # 打开个人卡片（点右上角显示名，只读）
            for cand in (settings.USERNAME, "陈方达"):
                try:
                    loc = p2.get_by_text(cand, exact=True).first
                    if loc.count() and loc.is_visible(timeout=2500):
                        loc.hover()
                        p2.wait_for_timeout(2000)
                        card = scan_prod(p2, "portal-card")
                        r["pages"]["portal-card"] = card
                        print("  card has客商:", card["has_keshang"], flush=True)
                        break
                except Exception:
                    continue
        except Exception as exc:  # noqa: BLE001
            r["portal_error"] = f"{type(exc).__name__}: {exc}"[:300]
            print("portal login failed:", r["portal_error"], flush=True)

        ctx.close()
        ctx2.close()
        b.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nWROTE {OUT}", flush=True)


if __name__ == "__main__":
    main()
