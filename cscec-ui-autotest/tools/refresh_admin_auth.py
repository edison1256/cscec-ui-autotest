"""生成管理员后门登录态 `auth_states/admin-<env>.json`。

背景：`BackdoorLoginPage.save_state()` 在工程内**没有任何调用者**，
`auth_states/admin-uat.json` 属历史一次性产物，无法再生。
客商写入闭环（审批 / 建删租户）需要管理员身份，故补此入口。

用法：
    ENV=uat  python tools/refresh_admin_auth.py
    ENV=pre  python tools/refresh_admin_auth.py

走的是后门直登（`/udpweb/portal/index.html#/login`），不经 4A/SSO——
因此即使管理员账号在 4A 侧不可用（UAT 实测如此），只要后门口令有效即可。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, ".")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.settings import settings  # noqa: E402
from pages.portal.backdoor_login_page import (  # noqa: E402
    BackdoorLoginError,
    BackdoorLoginPage,
)


def main() -> int:
    if not settings.ADMIN_USERNAME or not settings.ADMIN_PASSWORD:
        print("!! 未配置 ADMIN_USERNAME / ADMIN_PASSWORD，无法生成管理员登录态")
        return 2

    target: Path = settings.admin_auth_state_file
    print(f"ENV={settings.ENV}  admin={settings.ADMIN_USERNAME[:3]}***  目标={target}")

    with sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, channel=settings.BROWSER_CHANNEL)
        except Exception:
            b = p.chromium.launch(headless=True)
        ctx = b.new_context(
            viewport=settings.VIEWPORT,
            ignore_https_errors=True,
        )
        ctx.set_default_timeout(settings.DEFAULT_TIMEOUT)
        ctx.set_default_navigation_timeout(settings.NAVIGATION_TIMEOUT)
        page = ctx.new_page()

        try:
            login_page = BackdoorLoginPage(page).open().login()
            saved = login_page.save_state()
            info = {}
            try:
                info = login_page.read_login_info()
            except Exception:
                pass
            print(f"OK 登录态已写入: {saved}")
            if info:
                keep = ("userNo", "userName", "tenantName", "orgName")
                print("   " + json.dumps({k: info.get(k) for k in keep if k in info},
                                         ensure_ascii=False))
            return 0
        except BackdoorLoginError as exc:
            print(f"!! 后门登录失败: {exc}")
            print("   请确认 ADMIN_USERNAME / ADMIN_PASSWORD 是**后门口令**（非 4A 密码）")
            return 1
        except Exception as exc:  # noqa: BLE001
            print(f"!! 未预期错误: {type(exc).__name__}: {exc}")
            return 1
        finally:
            ctx.close()
            b.close()


if __name__ == "__main__":
    raise SystemExit(main())
