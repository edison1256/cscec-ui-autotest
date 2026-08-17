"""临时探测：UAT 门户首页导航结构（用完即删）。"""
import json

import pytest
from playwright.sync_api import Page

from pages.portal.portal_home_page import PortalHomePage


def _dump(page: Page, label: str):
    print(f"\n===== {label} | url={page.url} =====")
    # 顶部可见文字（nav / header / menu 容器）
    for sel in [
        "header", "nav", ".menu", ".topbar", ".header", "[class*='header']",
        "[class*='nav']", "[class*='menu']", "[class*='topbar']",
    ]:
        try:
            nodes = page.locator(sel).all()
            for n in nodes[:3]:
                txt = n.inner_text().replace("\n", " | ").strip()
                if txt:
                    print(f"  [{sel}] -> {txt[:200]}")
        except Exception as e:
            print(f"  [{sel}] ERR {e}")
    # 所有可见文字链接/按钮（含 控制台 / 管理后台 / 工作台 等）
    try:
        anchors = page.locator("a, button, [role='menuitem'], [class*='item']").all()
        texts = []
        for a in anchors:
            try:
                t = a.inner_text().strip()
                if t and len(t) <= 12:
                    texts.append(t)
            except Exception:
                pass
        print("  VISIBLE_LINKS:", " / ".join(sorted(set(texts))[:60]))
    except Exception as e:
        print(f"  VISIBLE_LINKS ERR {e}")


@pytest.mark.probe
def test_probe_portal(logged_in_page: Page):
    page = logged_in_page
    page.set_default_timeout(8000)
    portal = PortalHomePage(page)
    portal.open()
    page.wait_for_load_state("networkidle", timeout=8000)
    _dump(page, "PORTAL_HOME_AFTER_LOGIN")

    # 找 管理后台 并尝试点击
    for sel in [
        page.get_by_text("管理后台", exact=True),
        page.locator("[class*='topbar'] >> text=管理后台"),
        page.locator("a:has-text('管理后台')"),
        page.get_by_text("管理后台"),
    ]:
        try:
            sel.first.wait_for(state="visible", timeout=6000)
            print("\n>>> 点击 '管理后台'")
            sel.first.click()
            page.wait_for_load_state("networkidle", timeout=8000)
            page.wait_for_timeout(1500)
            _dump(page, "AFTER_CLICK_管理后台")
            break
        except Exception as e:
            print(f"  管理后台点击候选失败: {e}")

    print("\n>>> 尝试直接查找 控制台")
    for sel in [
        page.get_by_text("控制台", exact=True),
        page.locator("a:has-text('控制台')"),
        page.locator("[class*='item']:has-text('控制台')"),
    ]:
        try:
            sel.first.wait_for(state="visible", timeout=4000)
            print(f"  找到 控制台: {sel}")
            break
        except Exception:
            pass
    else:
        print("  未找到 控制台 入口")

    # 输出全部 href 含 console 的链接
    try:
        hrefs = page.eval_on_selector_all(
            "a[href]", "els => els.map(e => e.href).filter(h => /console|admin|manage|backend|workbench/i.test(h))"
        )
        print("  CONSOLE-LIKE HREFS:", json.dumps(hrefs[:20], ensure_ascii=False))
    except Exception as e:
        print(f"  HREF probe ERR {e}")

    assert True
