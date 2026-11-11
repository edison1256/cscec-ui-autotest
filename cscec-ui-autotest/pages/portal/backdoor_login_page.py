"""控制台后门直登页（账号密码直登，绕过 4A/SSO）。

用途：**仅环境装配类运维脚本**使用，例如给测试账号补租户成员关系与角色。
业务用例不得依赖本页面，必须继续走 ``pages/portal/login_page.py`` 的正式登录链路。

背景：
- 正式登录走 4A/SSO，需要 iframe 内表单（``#usernameIn`` / ``#pwdIn`` / ``#pwdLoginButton``）。
- 后门直登是控制台域下的 SPA 路由 ``/udpweb/portal/index.html#/login``，
  工程此前从未使用过，选择器未知，因此本类对每种控件都给多个候选并逐个试探。
- 登录失败时必须落下 HTML 与截图，否则无法定位，只能盲猜。

安全约定：
- 凭证只从 ``settings.ADMIN_USERNAME`` / ``settings.ADMIN_PASSWORD`` 读取。
- 登录态写入 ``auth_states/admin-<env>.json``（该目录已被 .gitignore 覆盖）。
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Frame, Page, TimeoutError as PWTimeout

from core.base_page import BasePage
from core.logger import get_logger
from config.settings import settings

logger = get_logger("backdoor_login_page")


class BackdoorLoginError(RuntimeError):
    """后门登录失败，携带诊断目录路径。"""


class BackdoorLoginPage(BasePage):
    """控制台后门直登页面。"""

    PAGE_NAME = "控制台后门登录页"

    # 后门表单是独立 SPA（antd），实测结构（2026-11-10 PRE）：
    #   input[type=text]      账号
    #   input[type=password]  密码
    #   input[type=checkbox]  记住密码
    #   button[type=submit]   文本「登 录」  <- 真正的账号密码登录
    #   button[type=button]   文本「4A登录」  <- SSO 跳转，**不是我们要的**
    # 教训：绝不能用 button:has-text('登录')，它会先命中「4A登录」并打到 CAS。
    _USERNAME_CANDIDATES = (
        "#usernameIn",
        "input[type='text']",
        "input[name='username']",
        "input[name='loginName']",
        "input[placeholder*='账号']",
        "input[placeholder*='用户名']",
    )
    _PASSWORD_CANDIDATES = (
        "#pwdIn",
        "input[type='password']",
        "input[name='password']",
        "input[name='pwd']",
    )
    _SUBMIT_CANDIDATES = (
        "button[type='submit']",
        "#pwdLoginButton",
        "button:has-text('登 录')",
        "[class*='loginButton']",
    )
    # 明确排除的按钮文案（SSO 入口，点了会跳 CAS 并报 Not Authorized）
    _SUBMIT_EXCLUDE_TOKENS = ("4A",)
    # 登录完成的判据：localStorage 里出现登录信息
    _LOGIN_INFO_KEY = "__login_info__"

    def __init__(self, page: Page):
        super().__init__(page)

    # ------------------------------------------------------------------
    # 诊断
    # ------------------------------------------------------------------
    @staticmethod
    def _diag_dir() -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = settings.REPORTS_DIR / "identity-provisioning" / f"backdoor-login-{stamp}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _dump(self, diag: Path, tag: str) -> None:
        """落盘现场：截图 + HTML + URL，便于事后定位选择器。"""
        try:
            (diag / f"{tag}.png").write_bytes(self.page.screenshot(full_page=True))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"截图失败({tag}): {exc}")
        try:
            (diag / f"{tag}.html").write_text(self.page.content(), encoding="utf-8")
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"HTML 落盘失败({tag}): {exc}")
        try:
            (diag / f"{tag}.url.txt").write_text(self.page.url, encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # 表单定位
    # ------------------------------------------------------------------
    @staticmethod
    def _first_visible(scope, candidates) -> object | None:
        for selector in candidates:
            try:
                locator = scope.locator(selector).first
                if locator.count() and locator.is_visible(timeout=1500):
                    return locator
            except Exception:  # noqa: BLE001
                continue
        return None

    def _submit_button(self, scope):
        """定位提交按钮，并显式排除「4A登录」等 SSO 入口。"""
        for selector in self._SUBMIT_CANDIDATES:
            try:
                locator = scope.locator(selector).first
                if not locator.count() or not locator.is_visible(timeout=1500):
                    continue
                text = ""
                try:
                    text = locator.inner_text() or ""
                except Exception:  # noqa: BLE001
                    pass
                if any(token in text for token in self._SUBMIT_EXCLUDE_TOKENS):
                    logger.info(f"[后门] 跳过 SSO 按钮({selector}, text={text!r})")
                    continue
                return locator, text
            except Exception:  # noqa: BLE001
                continue
        return None, ""

    def _form_scope(self) -> tuple[object, str]:
        """返回承载登录表单的作用域：优先主文档，其次可见 iframe。"""
        if self._first_visible(self.page, self._PASSWORD_CANDIDATES) is not None:
            return self.page, "main"
        for frame in self.page.frames:
            if frame == self.page.main_frame:
                continue
            if self._first_visible(frame, self._PASSWORD_CANDIDATES) is not None:
                return frame, f"frame:{frame.url[:120]}"
        return self.page, "main(fallback)"

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------
    def open(self) -> "BackdoorLoginPage":
        url = settings.ADMIN_LOGIN_URL
        if not url:
            raise BackdoorLoginError("settings.ADMIN_LOGIN_URL 为空，无法打开后门登录页")
        logger.info(f"[后门] 打开 {url}")
        self.page.goto(url, wait_until="domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT)
        # SPA 路由需要额外等待渲染
        time.sleep(2.0)
        return self

    def login(
        self,
        username: str | None = None,
        password: str | None = None,
    ) -> "BackdoorLoginPage":
        user = settings.ADMIN_USERNAME if username is None else username
        pwd = settings.ADMIN_PASSWORD if password is None else password
        if not user or not pwd:
            raise BackdoorLoginError(
                "管理员凭证缺失：请在 .env 配置 ADMIN_USERNAME / ADMIN_PASSWORD"
            )

        diag = self._diag_dir()
        self._dump(diag, "01-before-input")

        scope, scope_desc = self._form_scope()
        logger.info(f"[后门] 表单作用域: {scope_desc}")

        user_box = self._first_visible(scope, self._USERNAME_CANDIDATES)
        pwd_box = self._first_visible(scope, self._PASSWORD_CANDIDATES)
        if user_box is None or pwd_box is None:
            self._dump(diag, "02-form-not-found")
            raise BackdoorLoginError(
                f"未定位到账号/密码输入框。诊断目录: {diag}"
            )

        user_box.fill(user)
        pwd_box.fill(pwd)
        self._dump(diag, "03-filled")

        submit, submit_text = self._submit_button(scope)
        if submit is None:
            self._dump(diag, "04-submit-not-found")
            raise BackdoorLoginError(f"未定位到登录按钮。诊断目录: {diag}")

        logger.info(f"[后门] 点击提交按钮 text={submit_text!r}")
        submit.click()
        logger.info("[后门] 已提交登录表单")

        if not self._wait_logged_in():
            self._dump(diag, "05-login-failed")
            raise BackdoorLoginError(
                f"提交后未检测到登录态（{self._LOGIN_INFO_KEY}）。诊断目录: {diag}"
            )

        self._dump(diag, "06-logged-in")
        logger.info(f"[后门] 登录成功，诊断: {diag}")
        return self

    def _wait_logged_in(self, timeout_s: int = 40) -> bool:
        """等待出现登录态。逐域检查 localStorage，兼容登录后跳转主域。"""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                if self.page.evaluate(
                    "() => !!window.localStorage.getItem('__login_info__')"
                ):
                    return True
            except Exception:  # noqa: BLE001
                pass
            # 登录后可能跳到工作台/控制台首页
            if "/#/login" not in self.page.url and "login" not in self.page.url.lower():
                if "udpweb/portal/index.html" in self.page.url:
                    return True
            time.sleep(1.0)
        return False

    # ------------------------------------------------------------------
    # 登录态持久化
    # ------------------------------------------------------------------
    def save_state(self, path: Path | None = None) -> Path:
        target = path or settings.admin_auth_state_file
        target.parent.mkdir(parents=True, exist_ok=True)
        self.page.context.storage_state(path=str(target))
        logger.info(f"[后门] 登录态已写入 {target}")
        return target

    # ------------------------------------------------------------------
    # 身份读取
    # ------------------------------------------------------------------
    def read_login_info(self) -> dict:
        """读取 localStorage 中的 __login_info__，返回解析后的字典（失败返回空）。"""
        import json

        try:
            raw = self.page.evaluate(
                "() => window.localStorage.getItem('__login_info__')"
            )
        except Exception:  # noqa: BLE001
            return {}
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {"__raw__": str(raw)[:500]}


__all__ = ["BackdoorLoginPage", "BackdoorLoginError"]
