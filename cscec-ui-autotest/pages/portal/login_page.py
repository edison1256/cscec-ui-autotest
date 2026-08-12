"""
门户登录页 — 处理 iframe 内的登录表单

中建云登录流程：
1. 访问门户首页
2. 点击右上角"登录"链接
3. 进入 iframe 中的登录表单
4. 输入用户名/密码
5. 点击登录按钮
6. 返回 PortalHomePage
"""

from urllib.parse import urlparse
from typing import Optional

from playwright.sync_api import Page

from core.base_page import BasePage
from core.logger import get_logger
from config.settings import settings

logger = get_logger("login_page")


class LoginPage(BasePage):
    """门户登录页"""

    PAGE_NAME = "登录页"
    PAGE_URL = ""

    # ── Locators ──
    # 右上角登录入口
    _login_entry_candidates = [
        ("css", ".login-btn"),
        ("css", "a[href*='login']"),
        ("text", "登录"),
    ]
    # 登录表单 iframe
    _login_frame = "#qrcont"
    # iframe 内的表单元素
    _username_input = "#usernameIn"
    _password_input = "#pwdIn"
    _login_button = "#pwdLoginButton"

    def __init__(self, page: Page):
        super().__init__(page)

    @property
    def _portal_host(self) -> str:
        """当前环境门户域名。"""
        return urlparse(settings.BASE_URL).netloc.lower()

    def _current_host(self) -> str:
        return urlparse(self.page.url).netloc.lower()

    def _is_cas_login_url(self) -> bool:
        parsed = urlparse(self.page.url.lower())
        return (
            "iam" in parsed.netloc
            and "cas" in parsed.path
        ) or "passport" in parsed.netloc or "/login" in parsed.path

    # ── Actions ──

    def open(self) -> "LoginPage":
        """打开门户首页"""
        self.nav.goto_url(settings.BASE_URL)
        self.assertions.any_text_visible(["登录", "中国建筑"])
        return self

    def click_login_entry(self) -> "LoginPage":
        """点击右上角登录入口"""
        # 点击登录链接后页面会跳转到 CAS 认证页
        # 使用 expect_navigation 等待跳转完成
        try:
            with self.page.expect_navigation(wait_until="domcontentloaded", timeout=settings.NAVIGATION_TIMEOUT):
                self.elements.click_candidates(
                    self._login_entry_candidates,
                    description="登录入口",
                )
        except Exception:
            # 某些情况下点击可能不触发导航（如弹窗模式），直接继续
            self.elements.click_candidates(
                self._login_entry_candidates,
                description="登录入口",
            )
        # 等待登录表单 iframe 加载
        self.page.wait_for_selector(self._login_frame, timeout=settings.ACTION_TIMEOUT)
        # 等待 iframe 内容加载完成
        frame = self._get_login_frame()
        if frame:
            frame.wait_for_load_state("networkidle", timeout=settings.ACTION_TIMEOUT)
        return self

    def _get_login_frame(self):
        """获取登录 iframe 的 Frame 对象"""
        return self.page.frame(name="qrcont")

    def _fill_in_frame(self, selector: str, value: str, desc: str) -> "LoginPage":
        """在登录 iframe 内填充输入框

        防止 Chromium 自动填充（autocomplete）覆盖输入值：
        1. 先 fill 标准方式
        2. 短暂等待后验证
        3. 如果被覆盖，用 type 逐字输入
        """
        frame = self._get_login_frame()
        if frame:
            # 方式1: 标准 fill
            frame.fill(selector, value)
            # 等待可能的自动填充完成
            import time
            time.sleep(0.3)
            actual = frame.query_selector(selector).input_value()
            if actual != value:
                logger.warning(f"[登录表单] 填充 {desc} 后值被覆盖: 期望 '{value}', 实际 '{actual}'，使用 type 重输")
                # 先清空，再逐字输入
                frame.fill(selector, "")
                frame.type(selector, value, delay=30)
                time.sleep(0.2)
                actual2 = frame.query_selector(selector).input_value()
                logger.info(f"[登录表单] 重输后 {desc} 值: '{actual2}'")
            logger.debug(f"[登录表单] 填充 {desc}")
        else:
            # 降级：使用 frame_locator
            fl = self.page.frame_locator(self._login_frame)
            fl.locator(selector).fill(value)
            logger.debug(f"[登录表单] 填充 {desc}（via frame_locator）")
        return self

    def _click_in_frame(self, selector: str, desc: str) -> "LoginPage":
        """在登录 iframe 内点击"""
        frame = self._get_login_frame()
        if frame:
            frame.click(selector)
            logger.debug(f"[登录表单] 点击 {desc}")
        else:
            # 降级：使用 frame_locator
            fl = self.page.frame_locator(self._login_frame)
            fl.locator(selector).click()
            logger.debug(f"[登录表单] 点击 {desc}（via frame_locator）")
        return self

    def fill_credentials(
        self, username: Optional[str] = None, password: Optional[str] = None
    ) -> "LoginPage":
        """输入用户名和密码"""
        uname = settings.USERNAME if username is None else username
        pwd = settings.effective_password if password is None else password
        self._fill_in_frame(self._username_input, uname, "用户名")
        self._fill_in_frame(self._password_input, pwd, "密码")
        return self

    def click_login_button(self) -> "LoginPage":
        """点击登录按钮"""
        self._click_in_frame(self._login_button, "登录按钮")
        # 等待 CAS 认证完成并跳转回当前环境的门户首页
        try:
            self.page.wait_for_function(
                "host => window.location.host.toLowerCase() === host",
                arg=self._portal_host,
                timeout=settings.NAVIGATION_TIMEOUT,
            )
            self.page.wait_for_function(
                "() => !window.location.search.includes('code=') "
                "&& !!window.localStorage.getItem('__login_info__')",
                timeout=20000,
            )
        except Exception:
            # 如果 URL 等待超时，至少等待当前页面稳定，交给断言给出明确失败原因。
            try:
                self.page.wait_for_load_state("networkidle", timeout=5000)
            except Exception:
                pass
        logger.info(f"[登录] 点击登录按钮完成，当前 URL: {self.page.url}")
        return self

    def login(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ) -> "LoginPage":
        """
        完整登录流程

        Args:
            username: 用户名，默认使用配置中的
            password: 密码，默认使用配置中的

        Returns:
            self（已登录状态）
        """
        self.open()
        self.click_login_entry()
        self.fill_credentials(username, password)
        self.click_login_button()
        logger.info(f"[登录] 完成，当前 URL: {self.page.url}")
        return self

    # ── Assertions ──

    def should_be_on_login_page(self) -> "LoginPage":
        """断言当前在登录页"""
        # iframe 应该可见
        frame_loc = self.page.locator(self._login_frame)
        assert frame_loc.is_visible(), "登录表单 iframe 不可见"
        return self

    def should_login_succeed(self) -> "LoginPage":
        """断言登录成功（已离开 CAS 认证页，到达门户首页）"""
        # 判断标准：当前 host 已经回到目标门户，不再停留在 CAS/Passport 登录页。
        on_portal = self._current_host() == self._portal_host
        on_cas_login = self._is_cas_login_url()
        assert on_portal and not on_cas_login, \
            f"登录似乎未成功，当前仍停留在 CAS 认证页: {self.page.url}"
        logger.info("[断言] 登录成功")
        return self

    def should_login_fail(self) -> "LoginPage":
        """断言登录失败（应仍在登录页或看到错误提示）"""
        current_url = self.page.url.lower()
        still_on_login = self._is_cas_login_url() or "login" in current_url or "passport" in current_url
        # 或者检查错误提示
        error_visible = False
        try:
            error_loc = self.page.locator(
                ".ant-message-error, .ant-form-explain, .login-error, .ant-alert-error"
            ).first
            error_visible = error_loc.is_visible()
        except Exception:
            pass
        assert still_on_login or error_visible, \
            f"登录应失败但似乎成功了，当前 URL: {self.page.url}"
        logger.info("[断言] 登录失败（符合预期）")
        return self
