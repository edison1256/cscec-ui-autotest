"""门户登录页 — 兼容新版 4A/IDaaS 认证链路与旧版 iframe 表单。

## 为什么重写（2026-11-11 实测）

认证平台改版后，旧实现（`#qrcont` iframe + `#usernameIn`/`#pwdIn`/`#pwdLoginButton`）
在 UAT 已经完全失效。实测到的两条真实路径：

### A. 控制台域（irp-*，loginType=1）
```
https://irp-uat.cscec.com/  --302-->  iamuat.cscec.com/cas/login
```

### B. 门户/工作台域（cloud-*，loginType=2）
```
https://cloud-uat.cscec.com/            （营销门户）
  -> 点「登录」
  -> idaas-uat.cscec.com/sso/index.html/#/passport/login?redirect_uri=...
  -> 点「其它登录方式」
  -> 点 img[alt='4A']                    ← 4A 认证是**图标**，不是文字按钮
  -> iamuat.cscec.com/cas/login?client_id=...
```

### 两条路径的共同点（关键，别踩）
1. 真正的账号密码表单在 frame `authn/login.html` 内，**默认不可见**。
2. **必须先点「密码登录」tab**，否则只有一个隐藏的「短信验证」表单。
3. 表单渲染有延迟，立即 `is_visible()` 会全部返回 False —— **必须等约 6 秒**。
4. 必须用 `:visible` 伪类定位，否则会命中文档里的隐藏同名输入框。
5. 「4A登录」按钮文本含「登录」，`button:has-text('登录')` 会误点它并跳到 CAS
   报 `Application Not Authorized to Use CAS` —— 必须显式排除。

旧版 iframe 链路（prod/pre 可能仍是旧版）作为**兜底**保留，不影响新流程。
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from playwright.sync_api import Frame, Page

from core.base_page import BasePage
from core.logger import get_logger
from config.settings import settings

logger = get_logger("login_page")


class LoginPage(BasePage):
    """门户登录页（兼容新旧认证链路）。"""

    PAGE_NAME = "登录页"
    PAGE_URL = ""

    # ── 门户首页的登录入口 ──
    _login_entry_candidates = [
        ("css", ".login-btn"),
        ("css", "a[href*='login']"),
        ("text", "登录"),
    ]

    # ── IDaaS 页（loginType=2）──
    _idas_other_entry_labels = ("其它登录方式", "其他登录方式", "更多登录方式")
    _idas_4a_icon_selectors = (
        "img[alt='4A']",
        "img[src*='social/zj']",
    )

    # ── 4A/CAS 登录 frame ──
    _cas_frame_url_token = "authn/login.html"
    _cas_password_tab_labels = ("密码登录", "密码登陆")
    _cas_username_selectors = (
        "input[name='username']:visible",
        "input[placeholder*='手机号']:visible",
        "input[placeholder*='用户名']:visible",
        "input[type='text']:visible",
        "#usernameIn",
    )
    _cas_password_selectors = (
        "input[type='password']:visible",
        "input[name='password']:visible",
        "#pwdIn",
    )
    _cas_submit_selectors = (
        "button:has-text('登 录')",
        "button[type='submit']",
        "#pwdLoginButton",
        "button:has-text('登录')",
    )
    # 文本含这些的按钮一律跳过（SSO 入口，点了会跳 CAS 并报 Not Authorized）
    _submit_exclude_tokens = ("4A",)

    # ── 旧版 iframe 兜底 ──
    _legacy_login_frame = "#qrcont"
    _legacy_username_input = "#usernameIn"
    _legacy_password_input = "#pwdIn"
    _legacy_login_button = "#pwdLoginButton"

    # 表单渲染等待（实测约 3~6 秒）
    _form_render_timeout_ms = 25000
    _form_settle_ms = 6000

    def __init__(self, page: Page):
        super().__init__(page)
        # open() 使用的入口域名；默认控制台域，可被 cloud 域覆盖
        self._entry_base: str = settings.BASE_URL

    # ------------------------------------------------------------------
    # 环境判定
    # ------------------------------------------------------------------
    @property
    def _portal_host(self) -> str:
        """当前环境门户域名。"""
        return urlparse(settings.BASE_URL).netloc.lower()

    def _current_host(self) -> str:
        return urlparse(self.page.url).netloc.lower()

    def _url_of(self, page_or_frame) -> str:
        try:
            return (page_or_frame.url or "").lower()
        except Exception:  # noqa: BLE001
            return ""

    def _is_cas_login_url(self) -> bool:
        """是否停留在认证页（CAS / IAM / IDaaS passport）。"""
        url = self._url_of(self.page)
        parsed = urlparse(url)
        return (
            ("iam" in parsed.netloc and "cas" in parsed.path)
            or "passport" in parsed.netloc
            or "/login" in parsed.path
        )

    def _on_idas_page(self) -> bool:
        return "passport" in self._url_of(self.page) or "idaas" in self._current_host()

    # ------------------------------------------------------------------
    # 诊断
    # ------------------------------------------------------------------
    @staticmethod
    def _diag_dir() -> Path:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = settings.REPORTS_DIR / "login" / f"login-fail-{stamp}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _dump(self, diag: Path, tag: str) -> None:
        try:
            (diag / f"{tag}.png").write_bytes(self.page.screenshot(full_page=True))
        except Exception:  # noqa: BLE001
            pass
        try:
            (diag / f"{tag}.html").write_text(self.page.content(), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
        try:
            (diag / f"{tag}.url.txt").write_text(self.page.url, encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # 打开
    # ------------------------------------------------------------------
    def open(self, base_url: Optional[str] = None) -> "LoginPage":
        """打开环境入口。可能直接落到认证页，也可能停在门户首页。

        Args:
            base_url: 指定入口域名。默认用 ``settings.BASE_URL``（控制台域）。
                门户/工作台域（cloud-*）需显式传入 ``settings.PORTAL_BASE_URL``
                —— 实测两域 **SSO 不互通**，必须各登一次。
        """
        self._entry_base = base_url or settings.BASE_URL
        self.nav.goto_url(self._entry_base)
        self.page.wait_for_timeout(2500)
        logger.info(f"[登录] 打开 {self._entry_base} -> {self.page.url}")
        return self

    # ------------------------------------------------------------------
    # 找到 4A/CAS 的账号密码表单
    # ------------------------------------------------------------------
    def _find_cas_frame(self, timeout_ms: int | None = None) -> Optional[Frame]:
        """轮询查找承载账号密码表单的 frame。"""
        deadline = time.monotonic() + (timeout_ms or self._form_render_timeout_ms) / 1000
        while time.monotonic() < deadline:
            for frame in self.page.frames:
                if self._cas_frame_url_token in self._url_of(frame):
                    return frame
            self.page.wait_for_timeout(800)
        return None

    def _find_legacy_frame(self) -> Optional[Frame]:
        try:
            frame = self.page.frame(name="qrcont")
            if frame is not None:
                frame.locator(self._legacy_username_input).wait_for(
                    state="visible", timeout=3000
                )
                return frame
        except Exception:  # noqa: BLE001
            return None
        return None

    def _get_login_frame(self) -> Optional[Frame]:
        """优先新版 CAS frame，其次旧版 iframe。"""
        return self._find_cas_frame(timeout_ms=3000) or self._find_legacy_frame()

    def _wait_form_ready(self, frame: Frame) -> bool:
        """等待表单可交互：先切「密码登录」tab，再等输入框可见。"""
        # 1) 切 tab（新版页面默认可能停在「短信验证」）
        for label in self._cas_password_tab_labels:
            try:
                tab = frame.get_by_text(label, exact=True).first
                if tab.count() and tab.is_visible(timeout=2000):
                    tab.click()
                    logger.info(f"[登录] 切换到「{label}」tab")
                    break
            except Exception:  # noqa: BLE001
                continue

        # 2) 等渲染：实测约 6 秒，轮询到可见为止
        self.page.wait_for_timeout(self._form_settle_ms)
        deadline = time.monotonic() + self._form_render_timeout_ms / 1000
        while time.monotonic() < deadline:
            if self._first_visible(frame, self._cas_username_selectors) is not None:
                return True
            self.page.wait_for_timeout(1000)
        return False

    @staticmethod
    def _first_visible(scope, selectors) -> object | None:
        for selector in selectors:
            try:
                locator = scope.locator(selector).first
                if locator.count() and locator.is_visible(timeout=1200):
                    return locator
            except Exception:  # noqa: BLE001
                continue
        return None

    # ------------------------------------------------------------------
    # 登录入口点击（门户 -> IDaaS -> 4A）
    # ------------------------------------------------------------------
    def click_login_entry(self) -> "LoginPage":
        """从门户首页进入认证页；支持 IDaaS 中间页。"""
        # 已经在认证页（控制台域直跳 CAS）则无需点击
        if self._find_cas_frame(timeout_ms=2500) is not None:
            logger.info("[登录] 已在 4A 认证页，跳过入口点击")
            return self

        # 1) 门户首页点「登录」
        try:
            with self.page.expect_navigation(
                wait_until="domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT
            ):
                self.elements.click_candidates(
                    self._login_entry_candidates, description="登录入口"
                )
            logger.info(f"[登录] 已点击登录入口 -> {self.page.url}")
        except Exception:  # noqa: BLE001
            # 可能已通过跳转完成，或页面本身无需点击
            self.page.wait_for_timeout(3000)

        # 2) 等页面落到 IDaaS（SPA 路由跳转，不一定触发 navigation 事件）
        idas_ready = False
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self._on_idas_page():
                idas_ready = True
                break
            # 若已经直接出现 CAS 表单，说明无需 IDaaS 中间页
            if self._find_cas_frame(timeout_ms=1000) is not None:
                break
            self.page.wait_for_timeout(800)

        # 3) IDaaS 中间页：展开「其它登录方式」并点 4A 图标
        if idas_ready:
            self._click_idaas_4a()
        else:
            self.page.wait_for_timeout(1500)
            if self._on_idas_page():
                self._click_idaas_4a()

        # 4) 等 CAS frame 出现（找不到时交给 fill_credentials 报明确错误）
        frame = self._find_cas_frame()
        if frame is None:
            logger.warning(f"[登录] 未找到 CAS 表单 frame，当前 URL: {self.page.url}")
        return self

    def _click_idaas_4a(self, attempts: int = 3) -> None:
        """在 IDaaS 登录页点「4A认证」图标。"""
        for attempt in range(1, attempts + 1):
            logger.info(f"[登录] IDaaS 第 {attempt} 次尝试点 4A 认证")
            # 展开其它登录方式
            for label in self._idas_other_entry_labels:
                try:
                    loc = self.page.get_by_text(label, exact=True).first
                    if loc.count() and loc.is_visible(timeout=2500):
                        loc.click()
                        logger.info(f"[登录] 展开「{label}」")
                        self.page.wait_for_timeout(2500)
                        break
                except Exception:  # noqa: BLE001
                    continue

            # 点 4A 图标（注意：是 img，不是按钮文本）
            for selector in self._idas_4a_icon_selectors:
                try:
                    icon = self.page.locator(selector).first
                    if icon.count() and icon.is_visible(timeout=3000):
                        icon.click()
                        logger.info(f"[登录] 点击 4A 认证图标 ({selector})")
                        # 等跳转到 CAS
                        for _ in range(10):
                            if self._find_cas_frame(timeout_ms=800) is not None:
                                return
                            self.page.wait_for_timeout(1000)
                        logger.warning("[登录] 点击 4A 图标后未出现 CAS 表单")
                        return
                except Exception:  # noqa: BLE001
                    continue
            self.page.wait_for_timeout(2000)
        logger.warning("[登录] 未找到 4A 认证图标，继续尝试直接进入表单")

    # ------------------------------------------------------------------
    # 填表 / 提交
    # ------------------------------------------------------------------
    def _fill_value(self, target, selector: str, value: str, desc: str) -> None:
        """填值并校验，防止浏览器自动填充覆盖。"""
        target.fill(selector, value)
        time.sleep(0.3)
        try:
            actual = target.query_selector(selector).input_value()
        except Exception:  # noqa: BLE001
            actual = value
        if actual != value:
            logger.warning(f"[登录表单] {desc} 被覆盖，改为逐字输入")
            target.fill(selector, "")
            target.type(selector, value, delay=30)
        logger.debug(f"[登录表单] 已填 {desc}")

    def fill_credentials(
        self, username: Optional[str] = None, password: Optional[str] = None
    ) -> "LoginPage":
        """输入用户名和密码（兼容新旧表单）。"""
        uname = settings.USERNAME if username is None else username
        pwd = settings.effective_password if password is None else password
        if not uname or not pwd:
            raise AssertionError(
                "登录凭证缺失：请检查 .env 的 USERNAME 与 "
                f"{settings.ENV.upper()}_PASSWORD"
            )

        frame = self._find_cas_frame() or self._find_legacy_frame()
        if frame is None:
            diag = self._diag_dir()
            self._dump(diag, "01-no-login-frame")
            raise AssertionError(
                f"未找到登录表单（当前 URL: {self.page.url}）。诊断目录: {diag}"
            )

        ready = self._wait_form_ready(frame)
        if not ready:
            diag = self._diag_dir()
            self._dump(diag, "02-form-not-ready")
            raise AssertionError(
                f"登录表单未渲染出账号输入框（frame: {frame.url[:120]}）。"
                f"诊断目录: {diag}"
            )

        user_box = self._first_visible(frame, self._cas_username_selectors)
        pwd_box = self._first_visible(frame, self._cas_password_selectors)
        if user_box is None or pwd_box is None:
            diag = self._diag_dir()
            self._dump(diag, "03-missing-input")
            raise AssertionError(
                f"账号或密码框缺失（user={user_box is not None}, "
                f"pwd={pwd_box is not None}）。诊断目录: {diag}"
            )

        user_selector = self._selector_of(frame, self._cas_username_selectors)
        pwd_selector = self._selector_of(frame, self._cas_password_selectors)
        self._fill_value(frame, user_selector, uname, "用户名")
        self._fill_value(frame, pwd_selector, pwd, "密码")
        return self

    @staticmethod
    def _selector_of(scope, selectors) -> str:
        for selector in selectors:
            try:
                locator = scope.locator(selector).first
                if locator.count() and locator.is_visible(timeout=800):
                    return selector
            except Exception:  # noqa: BLE001
                continue
        return selectors[0]

    def click_login_button(self, expected_host: Optional[str] = None) -> "LoginPage":
        """点击登录按钮并等待回到门户域名。"""
        frame = self._find_cas_frame() or self._find_legacy_frame()
        if frame is None:
            diag = self._diag_dir()
            self._dump(diag, "04-no-frame-on-submit")
            raise AssertionError(f"提交时找不到登录表单。诊断目录: {diag}")

        button = None
        clicked_text = ""
        for selector in self._cas_submit_selectors:
            try:
                locator = frame.locator(selector).first
                if not locator.count() or not locator.is_visible(timeout=1200):
                    continue
                text = ""
                try:
                    text = (locator.inner_text() or "").strip()
                except Exception:  # noqa: BLE001
                    pass
                if any(token in text for token in self._submit_exclude_tokens):
                    logger.info(f"[登录] 跳过 SSO 按钮 {selector} text={text!r}")
                    continue
                button = locator
                clicked_text = text
                break
            except Exception:  # noqa: BLE001
                continue

        if button is None:
            diag = self._diag_dir()
            self._dump(diag, "05-no-submit")
            raise AssertionError(f"未找到登录按钮。诊断目录: {diag}")

        logger.info(f"[登录] 点击提交按钮 text={clicked_text!r}")
        button.click()

        target_host = expected_host or self._portal_host
        try:
            self.page.wait_for_function(
                "host => window.location.host.toLowerCase() === host",
                arg=target_host,
                timeout=settings.NAVIGATION_TIMEOUT,
            )
            # OAuth 回调会带 ?code=... 并触发一次导航；等它落地再继续，
            # 否则后续 evaluate 会遇到 Execution context destroyed。
            try:
                self.page.wait_for_url(
                    lambda url: "code=" not in url, timeout=20000
                )
            except Exception:  # noqa: BLE001
                pass
            self.page.wait_for_timeout(2000)
        except Exception:  # noqa: BLE001
            try:
                self.page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:  # noqa: BLE001
                pass

        logger.info(f"[登录] 提交完成，当前 URL: {self.page.url}")
        return self

    # ------------------------------------------------------------------
    # 完整流程
    # ------------------------------------------------------------------
    def login(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        base_url: Optional[str] = None,
    ) -> "LoginPage":
        """完整登录流程（自动适配新旧认证链路）。

        Args:
            username / password: 默认取 ``settings``。
            base_url: 登录入口域名。传 ``settings.PORTAL_BASE_URL`` 可登录
                cloud-* 工作台域（与控制台域 SSO 不互通，需单独登录）。
        """
        target = base_url or settings.BASE_URL
        self.open(target)
        self.click_login_entry()
        self.fill_credentials(username, password)
        self.click_login_button(expected_host=urlparse(target).netloc.lower())
        logger.info(f"[登录] 完成，当前 URL: {self.page.url}")
        return self

    def login_portal(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> "LoginPage":
        """登录门户/工作台域（cloud-*）。两域 SSO 不互通，需独立登录。"""
        return self.login(username, password, base_url=settings.PORTAL_BASE_URL)

    # ------------------------------------------------------------------
    # 断言
    # ------------------------------------------------------------------
    def login_form_visible(self, timeout: int = 2000) -> bool:
        return (
            self._find_cas_frame(timeout_ms=timeout) is not None
            or self._find_legacy_frame() is not None
        )

    def should_be_on_login_page(self) -> "LoginPage":
        assert self.login_form_visible(timeout=5000), "登录表单不可见"
        return self

    def should_login_succeed(self, expected_host: Optional[str] = None) -> "LoginPage":
        """断言登录成功。

        Args:
            expected_host: 期望回到的域名。默认 ``settings.BASE_URL`` 的 host；
                登录 cloud-* 时应显式传入（或用 ``login_portal`` 后再断言）。
        """
        target_host = (expected_host or self._portal_host).lower()
        # 给 OAuth 回调留出落地时间，避免在导航中途判定
        for _ in range(10):
            if self._current_host() == target_host:
                break
            self.page.wait_for_timeout(1000)
        on_portal = self._current_host() == target_host
        on_auth = self._is_cas_login_url()
        assert on_portal and not on_auth, (
            f"登录似乎未成功，当前 {self.page.url}，期望域名 {target_host}"
        )
        logger.info("[断言] 登录成功")
        return self

    def should_login_fail(self) -> "LoginPage":
        current_url = self.page.url.lower()
        still_on_login = (
            self._is_cas_login_url() or "login" in current_url or "passport" in current_url
        )
        error_visible = False
        try:
            error_loc = self.page.locator(
                ".ant-message-error, .ant-form-explain, .login-error, .ant-alert-error"
            ).first
            error_visible = error_loc.is_visible()
        except Exception:  # noqa: BLE001
            pass
        assert still_on_login or error_visible, (
            f"登录应失败但似乎成功了，当前 URL: {self.page.url}"
        )
        logger.info("[断言] 登录失败（符合预期）")
        return self
