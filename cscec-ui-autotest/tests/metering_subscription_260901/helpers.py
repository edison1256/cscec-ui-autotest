"""Shared navigation and assertion helpers for metering-subscription 260901.

All knowledge (routes, anchors, API patterns) verified against PRE on 2026-10-09
via scratch_recon1~7. Read-only interactions only.
"""

from __future__ import annotations

import re
import time

from playwright.sync_api import Page, Response, TimeoutError, expect

from config.settings import settings

# ---------------------------------------------------------------------------
# Environment constants
# ---------------------------------------------------------------------------
# 2026-11-11 修正：原先写死 cloud-pre / irp-pre，导致 UAT 运行会打到 PRE 域名。
# 改为按 settings.ENV 派生，PRE 取值与改动前完全一致。
from config.environments import METERING_SUIT_KEYS  # noqa: E402

_SUIT = METERING_SUIT_KEYS.get(settings.ENV, METERING_SUIT_KEYS["prod"])
# 注：METERING_SUIT_KEYS_ON_CONSOLE_DOMAIN 记录了一个重要事实 ——
# 控制台域名下的工作台套件 key 与门户域的 "portal" 不是同一个值。
# 但**不要用它去拼 URL 直达业务页**：那样会进入该账号本不该有的套件，
# 看到越权数据。正确做法始终是「导航到工作台首页 → 点击磁贴」。
PORTAL_ROOT = settings.PORTAL_BASE_URL
CONSOLE_ROOT = settings.CONSOLE_BASE_URL
WORKBENCH_URL = (
    f"{PORTAL_ROOT.rstrip('/')}/udpweb/portal/index.html"
    f"?#/portal/home/workbench?suitKey={_SUIT['workbench']}"
    f"&mc={_SUIT['workbench']}&mn=%E5%B7%A5%E4%BD%9C%E5%8F%B0&mt=module"
    f"&appTitle=%E5%B7%A5%E4%BD%9C%E5%8F%B0"
)
CONSOLE_URL = (
    f"{CONSOLE_ROOT.rstrip('/')}/udpweb/portal/index.html"
    f"?#/portal/home/workbench?suitKey={_SUIT['console']}"
    f"&mc={_SUIT['console']}&mn=%E6%8E%A7%E5%88%B6%E5%8F%B0&mt=module"
    f"&appTitle=%E6%8E%A7%E5%88%B6%E5%8F%B0"
)

# 个人视角账号的工作台首页（控制台域名 + 个人工作台套件）。
#
# 只到「工作台首页」，**绝不直接拼二级页路由**：黑盒测试必须模拟真实用户，
# 通过点击磁贴/菜单进入目标页。曾经用 `#/sub/resource/subscription/app/appInfo`
# 直链绕过点击，结果进到一个该账号本不该有的套件（suitKey=1899...727），
# 看到的是其他租户的数据 —— 那是越权视图，不是该账号的真实业务视图。
PERSONAL_WORKBENCH_URL = (
    f"{CONSOLE_ROOT.rstrip('/')}/udpweb/portal/index.html"
    f"#/portal/home/workbench?suitKey={_SUIT['workbench']}"
)

# API patterns verified in recon
AGGREGATE_WB_PAT = re.compile(r"/irp-api/irp-portal-workbench/quota-instance/aggregate")
AGGREGATE_CS_PAT = re.compile(
    r"/irp-api/irp-portal-console/quota-instance/aggregateForConsole"
)
SUBTABLE_PAT = re.compile(r"quota-instance/listByIds")
ORDER_PAT = re.compile(r"quota-instance-order/findByOrderIds")

# Anchor data verified on PRE.
# 2026-10-12 current data set (我的订阅-API订阅, 11-col entitlement list):
#   WPS服务组件 | 订阅服务 | IRP_中建云项目 | 技术与大数据平台项目组 |
#   2026-06-01 11:29:57 ~ 2030-06-01 11:29:57 | 可用 | 不限次数 | 0 | 不限次数
#   中建云0731组件 | 测试数字 | IRP_测试下发 | ... | 永久有效 | 可用 | 不限次数
ANCHOR_RESOURCE_WPS = "WPS服务组件"
ANCHOR_RESOURCE_TAG = "标签中心"
ANCHOR_RESOURCE_PERMANENT = "中建云0731组件"  # 永久有效锚点 (2026-10-12)
ANCHOR_TENANT_NAME = "技术与大数据平台项目组"
ANCHOR_TENANT_NO = "ZH_01_0000_0001_0001"
ANCHOR_ORDER_ID = "PO2025103015352000"
ANCHOR_APPLY_APP = "IRP_中建云项目"  # 2026-10-12: 我的订阅子表订阅应用
ANCHOR_APPLY_APP_LEGACY = "一体化资源平台项目"  # 旧版锚点，兼容保留
CS_ANCHOR_RESOURCE = "实际控制人"
CS_ANCHOR_APP = "国资委审计专用"

# Field contracts from the outline (verified against real pages)
PARENT_HEADERS = (
    "序号", "租户编码", "租户名称", "资源名称", "资源编码",
    "服务模式", "资源发布方", "订阅数量", "操作",
)
# V1.2 unified page (deployed 2026-10-10): workbench 我的订阅-API订阅 and
# 订阅中心-API列表 share this column set (no tenant columns, has 统计方式)
PARENT_HEADERS_UNIFIED = (
    "资源名称", "资源编码", "服务模式", "资源所属方", "订阅数量", "操作",
)
CHILD_HEADERS = (
    "资源名称", "服务模式", "订阅应用", "资源发布方", "生效时间",
    "截止时间", "可用状态", "总可调用额", "已调用额", "剩余调用额", "操作",
)
ORDER_HEADERS = ("订单ID", "订阅人", "订阅人所在组织", "生效时间", "操作")
QUERY_FIELD_LABELS = ("资源名称", "资源编码", "订阅时间")

SENSITIVE_TOKENS = ("AKSK", "AKSk", "aksk", "SecretKey", "secretKey", "secret_key")

RESULTS_DIR = settings.REPORTS_DIR / "metering260901"


# ---------------------------------------------------------------------------
# CAS login (shared by workbench + console; both IAM domains handled)
# ---------------------------------------------------------------------------
def _fill_cas_field(frame, sel: str, value: str) -> None:
    frame.fill(sel, value)
    time.sleep(0.4)
    actual = frame.eval_on_selector(sel, "e => e.value")
    if actual != value:
        frame.fill(sel, "")
        frame.type(sel, value, delay=40)
        time.sleep(0.3)


def cas_login(page: Page, root: str) -> None:
    """Login the given page via portal/console root. Reuses existing session.

    2026-11-11 修正：认证平台改版后，旧 `#qrcont` iframe 链路已失效
    （PRE 上会跳到 idaas-pre 的 passport 页并卡住）。这里改为复用统一的
    `LoginPage`，由它处理 IDaaS -> 「其它登录方式」-> `img[alt='4A']` -> CAS，
    以及「密码登录」tab 切换与延迟渲染。
    """
    if settings.ENV != "pre":
        raise ValueError("ENV_MISMATCH: PRE login is forbidden outside PRE")

    from pages.portal.login_page import LoginPage  # 局部导入，避免导入期副作用

    page.goto(root, wait_until="domcontentloaded", timeout=60000)
    time.sleep(2.5)
    if page.evaluate("() => !!window.localStorage.getItem('__login_info__')"):
        return

    LoginPage(page).login(base_url=root)


# ---------------------------------------------------------------------------
# 个人视角业务账号（可替换槽位）
# ---------------------------------------------------------------------------
def personal_login(page: Page) -> None:
    """以「个人视角业务账号」登录工作台。

    账号来自 `.env` 的 `METERING_USERNAME` / `METERING_PASSWORD`
    （支持 `METERING_<ENV>_USERNAME` 等按环境覆盖），不硬编码，便于换人。

    两条路径：
      - 未配置独立槽位 -> 沿用主账号 4A 登录（既有行为不变）
      - 配置了独立槽位 -> 后门登录。该账号在 4A 不可用（CAS 提交后停在登录页），
        且后门会话只在中建云控制台域名下有效。
    """
    if not settings.uses_metering_account:
        from pages.portal.login_page import LoginPage

        LoginPage(page).login_portal()
        return

    from pages.portal.backdoor_login_page import BackdoorLoginPage

    BackdoorLoginPage(page).open().login(
        settings.metering_username, settings.metering_password
    )
    time.sleep(2.5)
    # 登录后必弹「公告」弹窗，会遮挡磁贴与菜单点击。
    # 实测 `.ant-modal-close` 在 DOM 里存在但点不到，只有 Escape 有效。
    for _ in range(2):
        page.keyboard.press("Escape")
        time.sleep(0.9)


def uses_personal_account() -> bool:
    """当前是否启用个人视角业务账号（决定工作台入口走 irp 还是 cloud）。"""
    return settings.uses_metering_account


def open_personal_workbench(page: Page, timeout_s: int = 40) -> str | None:
    """打开个人视角工作台并返回形态（'zjy' / 'sz' / None）。

    黑盒路径：导航到工作台首页 → 点击页面上可见的「应用订阅」磁贴 → 读左侧菜单。
    不拼接二级页路由，不绕过点击 —— 直链会跳到该账号本不该有的套件，
    看到的可能是其他租户数据（越权视图），不能作为业务断言依据。

    返回 None 表示「该账号的工作台没有订阅菜单」，属真实环境结论，
    调用方应据此 skip 而不是断言失败。
    """
    try:
        page.goto("about:blank", wait_until="domcontentloaded", timeout=20000)
        page.goto(PERSONAL_WORKBENCH_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3.0)
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger(__name__).warning(f"[personal] 打开工作台失败: {exc}"[:200])
        return None

    deadline = time.time() + timeout_s
    while time.time() < deadline:
        shape = workbench_tenant_shape(page)
        if shape:
            return shape
        # 只在页面上找可见磁贴并点击（真实用户动作）
        try:
            tile = page.get_by_text("应用订阅", exact=True).filter(visible=True).first
            if tile.count():
                tile.click()
                time.sleep(2.5)
                continue
        except Exception:  # noqa: BLE001
            pass
        time.sleep(1.5)
    return None


def safe_goto(page: Page, url: str, tries: int = 3) -> None:
    for i in range(tries):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(2)
            return
        except Exception:
            time.sleep(3)
    page.goto(url, wait_until="domcontentloaded", timeout=60000)


# ---------------------------------------------------------------------------
# Click helpers
# ---------------------------------------------------------------------------
def click_when_visible(page: Page, text: str, timeout_ms: int = 10000) -> bool:
    """Click exact text in whatever frame shows it, polling until deadline."""
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        for fr in page.frames:
            try:
                btn = fr.get_by_text(text, exact=True).first
                if btn.is_visible(timeout=600):
                    btn.click()
                    return True
            except Exception:
                continue
        time.sleep(0.4)
    return False


def click_text_strict(page: Page, text: str, timeout_ms: int = 8000) -> bool:
    """Click a visible, non-<title> exact-text element (avoids <title> hits)."""
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        for fr in page.frames:
            try:
                loc = fr.get_by_text(text, exact=True)
                for i in range(min(loc.count(), 8)):
                    el = loc.nth(i)
                    try:
                        if not el.is_visible(timeout=400):
                            continue
                        if (el.evaluate("e => e.tagName") or "").upper() == "TITLE":
                            continue
                        el.click()
                        return True
                    except Exception:
                        continue
            except Exception:
                continue
        time.sleep(0.4)
    return False


def open_menu(page: Page, *titles: str) -> None:
    """Click through menu titles sequentially."""
    for t in titles:
        ok = click_when_visible(page, t, timeout_ms=10000)
        assert ok, f"菜单项不可点击: {t}"
        time.sleep(1.2)


def open_api_subscription_workbench(page: Page) -> Response | None:
    """Workbench: 我的订阅 -> API订阅; returns aggregate API response if captured.

    双路径：
      - 主账号（4A）：先钉住 zjy 租户形态，再 goto 门户工作台首页点磁贴；
      - 个人账号（后门）：直接 goto 控制台域的「我的订阅」二级页路由，
        因为后门会话只在控制台 origin 有效，goto 门户域会掉登录。

    两条路径的终态一致：左侧有「我的订阅」，点「API订阅」后表格就绪。
    """
    if uses_personal_account():
        return _open_api_sub_personal(page)

    if not ensure_tenant(page, "zjy"):
        raise AssertionError("无法确保中建云租户形态（我的订阅菜单）")
    response = None
    try:
        with page.expect_response(
            lambda r: bool(AGGREGATE_WB_PAT.search(r.url)), timeout=20000
        ) as resp_info:
            open_menu(page, "我的订阅", "API订阅")
        response = resp_info.value
    except TimeoutError:
        # 页面可能复用已加载 chunk，aggregate 已发完；退化为等待表格渲染
        pass
    assert wait_list_ready(page), "工作台 API订阅表格未渲染"
    return response


def _click_left_menu(page: Page, label: str, timeout_ms: int = 10000) -> bool:
    """点左侧菜单叶子项，避开顶部 tab。

    顶部会同时存在同名 tab（如「API订阅 ×」），按文本取 first 容易点错。
    左侧菜单在 DOM 中位于内容区之后，故取 last，并优先用 menuitem 语义定位。
    """
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        for factory in (
            lambda: page.get_by_role("menuitem", name=label, exact=True).last,
            lambda: page.get_by_text(label, exact=True).last,
        ):
            try:
                loc = factory()
                if loc.count() and loc.is_visible(timeout=1500):
                    loc.click()
                    time.sleep(2.5)
                    return True
            except Exception:  # noqa: BLE001
                continue
        time.sleep(0.6)
    return False


def _open_api_sub_personal(page: Page) -> Response | None:
    """个人账号路径：控制台域二级页 -> 我的订阅 -> API订阅。

    注意必须先展开「我的订阅」父菜单：二级页默认停在「应用订阅」，
    未展开时 DOM 里没有「API订阅」叶子，直接点会落到顶部 tab 或无效。
    """
    shape = open_personal_workbench(page)
    if shape != "zjy":
        raise AssertionError(
            f"个人工作台未进入「我的订阅」形态（shape={shape}）；"
            "请确认 METERING_USERNAME 对应账号在目标租户下可用"
        )
    # 展开父菜单（若已是展开态，点击不会产生副作用）
    _click_left_menu(page, "我的订阅", timeout_ms=6000)
    time.sleep(1.2)
    response = None
    clicked = False
    try:
        with page.expect_response(
            lambda r: bool(AGGREGATE_WB_PAT.search(r.url)), timeout=15000
        ) as resp_info:
            clicked = _click_left_menu(page, "API订阅", timeout_ms=10000)
        response = resp_info.value
    except TimeoutError:
        # 接口可能已在进入二级页时发完，此时只需确保菜单已切换
        if not clicked:
            _click_left_menu(page, "API订阅", timeout_ms=10000)
    time.sleep(2.5)
    assert wait_list_ready(page), "个人工作台 API订阅表格未渲染"
    return response


def open_api_list_console(page: Page) -> Response | None:
    """Console: 订阅服务 -> API列表; returns aggregateForConsole response."""
    ensure_tenant(page, "zjy")
    page.goto("about:blank", wait_until="domcontentloaded", timeout=30000)
    page.goto(CONSOLE_URL, wait_until="domcontentloaded", timeout=60000)
    time.sleep(2.5)
    response = None
    try:
        with page.expect_response(
            lambda r: bool(AGGREGATE_CS_PAT.search(r.url)), timeout=20000
        ) as resp_info:
            open_menu(page, "订阅服务", "API列表")
        response = resp_info.value
    except TimeoutError:
        pass
    assert wait_list_ready(page), "控制台 API列表表格未渲染"
    return response


def wait_list_ready(page: Page, timeout_s: int = 25) -> bool:
    """Wait until the aggregate list table renders.

    Header markers across PRE iterations:
    - 2026-10-09 legacy: 租户编码
    - 2026-10-10 unified: 资源所属方
    - 2026-10-12 current: 资源发布方 (+ 11-col entitlement list for 我的订阅)
    "资源名称" is present in every iteration → primary marker.
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        for marker in ("资源名称", "资源所属方", "资源发布方", "租户编码"):
            try:
                if page.get_by_text(marker, exact=True).first.is_visible(timeout=800):
                    time.sleep(1.0)
                    return True
            except Exception:
                pass
        time.sleep(0.5)
    return False


def list_is_empty(page: Page) -> bool:
    """Detect the unified page empty state (暂无数据)."""
    try:
        body = visible_texts(page)
    except Exception:
        return False
    return "暂无数据" in body


# ---------------------------------------------------------------------------
# Assertions
# ---------------------------------------------------------------------------
def visible_texts(page: Page, selector: str = "body") -> str:
    """Read rendered text; a read failure must not pass negative assertions."""
    return page.locator(selector).inner_text(timeout=5000)


def assert_headers_present(page: Page, headers: tuple[str, ...], ctx: str) -> None:
    table_with_headers(page, headers, ctx)


def table_with_headers(page: Page, headers: tuple[str, ...], ctx: str):
    """Find one visible table satisfying the field contract, not page text."""
    actual = []
    for table in page.locator("table").all():
        if not table.is_visible():
            continue
        names = tuple(cell.inner_text().strip() for cell in table.locator("thead").first.locator("th").all())
        actual.append(names)
        if all(header in names for header in headers):
            return table, names
    raise AssertionError(f"{ctx} 缺失表头: {headers}; 实际表头: {actual}")


def entitlement_rows(page: Page) -> list[dict[str, str]]:
    return table_rows(page, CHILD_HEADERS, "权益账户子表")


def table_rows(page: Page, required: tuple[str, ...], ctx: str) -> list[dict[str, str]]:
    table, headers = table_with_headers(page, required, ctx)
    rows = []
    for row in table.locator("tbody").first.locator(":scope > tr").all():
        cells = row.locator(":scope > td").all()
        if row.is_visible() and len(cells) == len(headers):
            rows.append(dict(zip(headers, (cell.inner_text().strip() for cell in cells))))
    assert rows, f"{ctx}没有可核验的数据行"
    return rows


def assert_entitlement_toggle(page: Page, cycles: int = 3) -> None:
    parent, _ = table_with_headers(page, PARENT_HEADERS_UNIFIED, "API父表")
    row = parent.locator("tbody").first.locator(":scope > tr").first
    action = row.get_by_text(re.compile(r"^(查看|收起)$")).first
    for _ in range(cycles):
        action.click()
        expect(page.locator("thead").get_by_text("总可调用额", exact=True).last).to_be_visible()
        child, _ = table_with_headers(page, CHILD_HEADERS, "权益账户子表")
        expect(child).to_be_visible()
        action.click()
        expect(child).to_be_hidden()


def expand_first_row(page: Page) -> bool:
    """Click the first 查看 action and wait until the child table renders."""
    if not click_when_visible(page, "查看", timeout_ms=8000):
        return False
    # 稳态等待：子表渲染完成的标志是“查看订单明细”或“收起”出现
    deadline = time.time() + 10
    while time.time() < deadline:
        body = visible_texts(page)
        if "查看订单明细" in body or "收起" in body:
            time.sleep(1.0)
            return True
        time.sleep(0.5)
    return False


def page_contains_any(page: Page, *kws: str) -> tuple[str, ...]:
    body = visible_texts(page)
    return tuple(kw for kw in kws if kw in body)


# ---------------------------------------------------------------------------
# Tenant context (same account, two tenant shapes)
# ---------------------------------------------------------------------------
# 形态判定依据：工作台里是否出现「订阅中心」(sz) 或「我的订阅」(zjy)。
#
# 2026-11-11 实测修正：原值 zjy="中建云" 已失效（账号已不在该租户）。
# 实测同一租户名在 PRE / UAT 会给出**不同形态**，故改为按环境从
# config.environments.METERING_TENANTS 读取，见该处注释与证据路径。
from config.environments import METERING_DISPLAY_NAME, METERING_TENANTS  # noqa: E402

_TENANT_MAP = METERING_TENANTS.get(settings.ENV, METERING_TENANTS["prod"])
TENANT_ZJY = _TENANT_MAP["zjy"]
TENANT_SZ = _TENANT_MAP["sz"]
ACCOUNT_DISPLAY_NAME = METERING_DISPLAY_NAME.get(settings.ENV, "陈方达")

SWITCH_DIALOG_ANCHOR = "切换租户"


def workbench_tenant_shape(page: Page) -> str | None:
    """Detect current workbench menu shape: 'zjy' / 'sz' / None(unknown)."""
    try:
        body = visible_texts(page)
    except Exception:
        return None
    if "订阅中心" in body:
        return "sz"
    if "我的订阅" in body:
        return "zjy"
    return None


def _open_account_hover(page: Page) -> bool:
    # 优先用显示名文本触发（实测 hover 面板由显示名触发，class 匹配不稳定）
    candidates = (f"text={ACCOUNT_DISPLAY_NAME}", "text=陈方达",
                  "[class*='avatar']", "[class*='user']")
    for cand in candidates:
        try:
            loc = page.locator(cand).first
            if loc.is_visible(timeout=2500):
                loc.hover(timeout=3000)
                time.sleep(1.2)
                return True
        except Exception:
            continue
    return False


def switch_tenant(page: Page, tenant_name: str) -> bool:
    """Switch tenant via hover window: 切换租户 -> tenant list click."""
    page.goto(PORTAL_ROOT, wait_until="domcontentloaded", timeout=60000)
    time.sleep(2.5)
    if not _open_account_hover(page):
        return False
    if not click_when_visible(page, SWITCH_DIALOG_ANCHOR, timeout_ms=5000):
        return False
    time.sleep(1.5)
    if not click_when_visible(page, tenant_name, timeout_ms=6000):
        return False
    time.sleep(4)
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except Exception:
        pass
    return True


def _open_app_subscription(page: Page, timeout_s: int = 25) -> bool:
    """在工作台首页点「应用订阅」磁贴，直到二级页菜单出现。

    2026-11-12 加固：原实现只等固定 2.5s 后点一次磁贴，页面慢时磁贴还没渲染
    就直接跳过，导致形态检测为 None，进而误报「无法切换租户」（实测在 M2.2.5
    稳定复现）。改为轮询：磁贴出现就点，菜单出现就返回。
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            body = visible_texts(page)
            if "我的订阅" in body or "订阅中心" in body:
                return True
        except Exception:
            pass
        try:
            tile = page.get_by_text("应用订阅", exact=True).filter(visible=True).first
            if tile.count():
                tile.click()
                time.sleep(2.0)
                continue
        except Exception:
            pass
        time.sleep(1.0)
    return False


def _goto_workbench(page: Page, timeout_s: int = 30) -> str | None:
    """打开工作台并进入「应用订阅」二级页，返回检测到的形态（'zjy'/'sz'/None）。"""
    page.goto("about:blank", wait_until="domcontentloaded", timeout=30000)
    page.goto(WORKBENCH_URL, wait_until="domcontentloaded", timeout=60000)
    deadline = time.time() + timeout_s
    detected = None
    while time.time() < deadline:
        detected = workbench_tenant_shape(page)
        if detected:
            return detected
        # 菜单未出现时，尝试点一次「应用订阅」再判
        try:
            tile = page.get_by_text("应用订阅", exact=True).filter(visible=True).first
            if tile.count():
                tile.click()
                time.sleep(2.0)
        except Exception:
            pass
        time.sleep(1.5)
    return detected


def open_workbench_menu(page: Page, label: str, timeout_ms: int = 15000) -> bool:
    """打开工作台 -> 应用订阅 -> 点击目标菜单（我的订阅 / 组件订阅 …）。

    替代测试里「goto(WORKBENCH_URL) 后直接 click(我的订阅)」的写法：
    工作台首页是应用中心，只有磁贴，不含这些菜单，直接点必然失败。
    """
    _goto_workbench(page)
    return click_when_visible(page, label, timeout_ms=timeout_ms)


def ensure_tenant(page: Page, shape: str) -> bool:
    """Ensure workbench is in the given tenant shape ('zjy' or 'sz').

    Returns True when the target shape is active afterwards.
    """
    target_tenant = TENANT_SZ if shape == "sz" else TENANT_ZJY
    # _goto_workbench 内部已轮询到菜单出现并返回形态，无需再重复检测
    if _goto_workbench(page) == shape:
        return True
    if not switch_tenant(page, target_tenant):
        return False
    return _goto_workbench(page) == shape


def open_subscription_center(page: Page) -> Response | None:
    """中建数字 tenant: 订阅中心 -> API列表 (M2 module entry)."""
    if not ensure_tenant(page, "sz"):
        raise AssertionError("无法切换到中建数字租户（订阅中心形态）")
    response = None
    try:
        with page.expect_response(
            lambda r: bool(AGGREGATE_WB_PAT.search(r.url)), timeout=20000
        ) as resp_info:
            open_menu(page, "订阅中心", "API列表")
        response = resp_info.value
    except Exception:
        pass
    wait_list_ready_sc(page)
    return response


def wait_list_ready_sc(page: Page, timeout_s: int = 25) -> bool:
    """订阅中心列表渲染标志：资源名称表头出现（跨版本通用，见 wait_list_ready）。"""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        for marker in ("资源名称", "资源所属方", "资源发布方"):
            try:
                if page.get_by_text(marker, exact=True).first.is_visible(timeout=800):
                    time.sleep(1.0)
                    return True
            except Exception:
                pass
        time.sleep(0.5)
    return False


def expand_row_containing(page: Page, text: str, timeout_s: int = 20) -> bool:
    """展开包含指定文本的那个父行（点该行内的「查看」）。

    2026-11-12 新增：`click_when_visible(page, "查看")` 点的是**第一行**，
    若锚点资源在后面的行，展开的就是别的资源，子表里自然找不到目标值
    （实测 M7.4.3 因此误报「子表未展示订阅应用」）。
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            rows = page.locator("tr")
            for i in range(min(rows.count(), 60)):
                row = rows.nth(i)
                try:
                    if text not in row.inner_text():
                        continue
                    btn = row.get_by_text("查看", exact=True).first
                    if btn.count() and btn.is_visible():
                        btn.click()
                        time.sleep(3.0)
                        return True
                except Exception:
                    continue
        except Exception:
            pass
        time.sleep(1.0)
    return False


def wait_spin_gone(page: Page, timeout_s: int = 20) -> bool:
    """等待 antd loading 遮罩消失。

    2026-11-12 新增：查询/切换后页面会盖一层 `.ant-spin-spinning`，
    遮罩期间输入框虽然能被定位到，但 Playwright 判定为不可交互，
    `fill` 会一直重试到超时（实测报 `element is not visible`）。
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            if page.locator(".ant-spin-spinning").count() == 0:
                return True
            page.locator(".ant-spin-spinning").last.wait_for(state="hidden", timeout=3000)
            return True
        except Exception:
            time.sleep(0.4)
    return False


def gateway_error(page: Page) -> bool:
    """Detect pre-env gateway/micro-app load failures (502/qiankun)."""
    body = visible_texts(page)
    return (
        "502" in body
        and "Bad Gateway" in body
    ) or "You need to export lifecycle functions" in body
