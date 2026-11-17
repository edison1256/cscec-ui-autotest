"""最小复现：门户 → 显示名 → 切换租户 → 中建云控制台空间。

逐步打印，定位卡在哪一步（显示名 / 切换租户 / 控制台空间）。
只读，只点击视图切换。
"""

import sys

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.login_page import LoginPage  # noqa: E402


def main() -> None:
    if settings.ENV != "prod":
        raise SystemExit("必须 ENV=prod")

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
            print(f"1) 门户 URL: {page.url[:120]}")

            info = page.evaluate(
                "() => { const s = localStorage.getItem('__login_info__');"
                " return s ? JSON.parse(s) : null; }"
            )
            print(f"2) login_info: {info}")
            name = (info or {}).get("userName")
            print(f"3) 显示名: {name!r}")

            if name:
                loc = page.get_by_text(name, exact=True).first
                print(f"4) 显示名元素 count={loc.count()}")
                if loc.count():
                    loc.hover()
                    page.wait_for_timeout(2500)
                    body = page.locator("body").inner_text()
                    print(f"5) hover 后是否出现「切换租户」: {'切换租户' in body}")
                    # 打印含「切换」的行
                    hits = [x.strip() for x in body.splitlines() if "切换" in x or "空间" in x]
                    print(f"   相关文本: {hits[:8]}")

            # 尝试点切换租户
            sw = page.get_by_text("切换租户", exact=True).last
            print(f"6) 切换租户 locator count={sw.count()}")
            if sw.count():
                sw.click()
                page.wait_for_timeout(3500)
                body = page.locator("body").inner_text()
                print(f"7) 面板打开，是否含「中建云控制台空间」: {'中建云控制台空间' in body}")
                spaces = [x.strip() for x in body.splitlines()
                          if "空间" in x or "租户" in x][:12]
                print(f"   空间清单: {spaces}")
                print(f"   URL: {page.url[:130]}")

                target = page.get_by_text("中建云控制台空间", exact=True).last
                print(f"8) 控制台空间 count={target.count()}")
                if target.count():
                    before_pages = len(ctx.pages)
                    target.click()
                    page.wait_for_timeout(6000)
                    print(f"9) 点击后 pages {before_pages} -> {len(ctx.pages)}")
                    active = ctx.pages[-1]
                    print(f"   当前 URL: {active.url[:140]}")
                    try:
                        info2 = active.evaluate(
                            "() => { const s = localStorage.getItem('__login_info__');"
                            " return s ? JSON.parse(s) : null; }"
                        )
                    except Exception as e:
                        info2 = f"读取失败 {e}"
                    print(f"   进入后 login_info: {info2}")
        except Exception as exc:  # noqa: BLE001
            print(f"!! 异常: {type(exc).__name__}: {exc}"[:300])
        finally:
            ctx.close()
            b.close()


if __name__ == "__main__":
    main()
