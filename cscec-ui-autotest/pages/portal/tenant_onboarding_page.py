"""门户侧「租户开通」Page Object（客商接入 M02 / M03）。

覆盖黑盒路径（2026-11-13 生产、2026-11-16 UAT 双环境实测一致）：

    cloud 登录 → 右上角 hover 显示名 → 个人卡片 → 切换租户
      → 面板底部「+ 创建租户」→「申请创建租户」弹窗

设计约束：
- **纯黑盒**：只点可见入口，不拼二级页 URL。
  曾经用 `#/sub/resource/subscription/app/appInfo?suitKey=...` 直链绕过点击，
  进到该账号本不该有的套件并看到越权数据（详见 .workbuddy/memory/MEMORY.md 铁律）。
- **只读优先**：`dialog_structure()` 只读文本与按钮状态，绝不点击「确认提交」。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from core.base_page import BasePage
from config.settings import settings
from core.execution_contract import PrerequisiteResult

# 企业/租户状态词（UAT 与生产共用）
STATUS_WORDS = ("已开通", "未开通", "申请中", "未认证", "已认证", "审核中")

# 创建租户弹窗必须出现的 8 项要素（大纲 M03-L13）
DIALOG_REQUIRED_LABELS = (
    "申请创建租户",
    "租户管理员",
    "申请说明",
    "确认提交",
)


@dataclass(frozen=True)
class TenantRow:
    """切换租户面板中的一条租户记录。"""

    name: str
    states: tuple[str, ...]

    @property
    def opened(self) -> bool:
        return "已开通" in self.states

    @property
    def applying(self) -> bool:
        return "申请中" in self.states


@dataclass
class DialogSnapshot:
    """创建租户弹窗的结构快照（只读）。"""

    title_present: bool = False
    has_tree: bool = False
    has_admin: bool = False
    has_phone: bool = False
    has_desc: bool = False
    has_declaration: bool = False
    has_cancel: bool = False
    has_submit: bool = False
    submit_disabled: bool | None = None
    tenant_name_readonly: bool | None = None
    enterprises: list[dict] = field(default_factory=list)
    text: str = ""

    @property
    def missing(self) -> list[str]:
        checks = {
            "标题:申请创建租户": self.title_present,
            "企业组织树": self.has_tree,
            "租户管理员": self.has_admin,
            "管理员手机号": self.has_phone,
            "申请说明": self.has_desc,
            "声明勾选": self.has_declaration,
            "取消按钮": self.has_cancel,
            "提交按钮": self.has_submit,
        }
        return [k for k, v in checks.items() if not v]


class TenantOnboardingPage(BasePage):
    """客商接入：个人卡片 / 切换租户 / 创建租户申请。"""

    PAGE_NAME = "租户开通"

    CARD_TEXTS = ("账号", "租户", "待办", "常用工具")

    def __init__(self, page) -> None:
        super().__init__(page)
        self._tenant_rows: tuple[TenantRow, ...] = ()
        self._dialog: DialogSnapshot | None = None

    # ---------------- 导航 ----------------

    def current_display_name(self) -> str | None:
        """从登录态读当前用户显示名（页面右上角展示的是姓名，不是账号）。"""
        try:
            info = self.page.evaluate(
                "() => { const s = localStorage.getItem('__login_info__');"
                " return s ? JSON.parse(s) : null; }"
            )
        except Exception:
            return None
        if not isinstance(info, dict):
            return None
        for key in ("userName", "userRealName", "realName", "nickName"):
            value = info.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    def ensure_portal(self) -> "TenantOnboardingPage":
        """确保当前页在门户域。

        `logged_in_page` 只创建带登录态的上下文，页面本身仍是 about:blank；
        必须先导航到门户首页，否则既没有显示名也没有 localStorage。
        """
        url = (self.page.url or "").lower()
        if url.startswith("about:") or "cloud" not in url:
            self.page.goto(
                settings.PORTAL_BASE_URL,
                wait_until="domcontentloaded",
                timeout=settings.NAVIGATION_TIMEOUT,
            )
            self.page.wait_for_timeout(3000)
            # 关闭可能的公告/引导弹窗，避免遮挡右上角
            for _ in range(2):
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(600)
        return self

    def open_personal_card(self, display_name: str | None = None) -> "TenantOnboardingPage":
        """hover 右上角显示名，展开个人卡片。

        显示名优先级：显式入参 → localStorage 的 __login_info__.userName
        → 客商槽位账号。**不能用账号去匹配**：页面右上角渲染的是姓名。
        """
        self.ensure_portal()
        # 清掉可能残留的弹窗/面板，否则会遮挡右上角显示名
        self.close_dialogs(times=1)
        candidates: list[str] = []
        if display_name:
            candidates.append(display_name)
        resolved = self.current_display_name()
        if resolved:
            candidates.append(resolved)
        if settings.keshang_username:
            candidates.append(settings.keshang_username)

        tried: list[str] = []
        for cand in dict.fromkeys(candidates):
            tried.append(cand)
            try:
                loc = self.page.get_by_text(cand, exact=True).first
                if loc.count() and loc.is_visible(timeout=settings.ACTION_TIMEOUT):
                    loc.hover()
                    self.page.wait_for_timeout(2000)
                    return self
            except Exception:
                continue
        raise AssertionError(
            f"未找到可 hover 的显示名；已尝试 {tried}。"
            "页面右上角通常渲染姓名（__login_info__.userName）"
        )

    def open_tenant_switcher(self) -> tuple[TenantRow, ...]:
        """打开「切换租户」面板并解析租户列表。"""
        if not self._click("切换租户"):
            raise AssertionError("个人卡片中未找到「切换租户」入口")
        self.page.wait_for_timeout(2500)
        self._tenant_rows = self._parse_tenants()
        return self._tenant_rows

    def open_create_tenant_dialog(self) -> DialogSnapshot:
        """点「+ 创建租户」打开申请弹窗（只读，不提交）。"""
        if not self._click("创建租户"):
            raise AssertionError("切换租户面板中未找到「创建租户」入口")
        self.page.wait_for_timeout(3000)
        self._dialog = self.read_dialog()
        return self._dialog

    # ---------------- 读取 ----------------

    def read_dialog(self) -> DialogSnapshot:
        """读取当前弹窗结构，不触发任何写入。"""
        snap = DialogSnapshot()
        # 只抓弹窗容器：整页 body 文本很长，截断后会丢掉弹窗下半部分
        # （实测「租户名称」「掩码手机号」因此读不到）。
        text = ""
        for sel in ("[role='dialog']", ".ant-modal-content", ".ant-modal",
                    "[class*='modal-content']", "[class*='dialog']"):
            try:
                loc = self.page.locator(sel).first
                if loc.count():
                    candidate = loc.inner_text()
                    if candidate and len(candidate) > 20:
                        text = candidate
                        break
            except Exception:
                continue
        if not text:
            try:
                text = self.page.locator("body").inner_text()
            except Exception:
                text = ""
        snap.text = text[:6000]

        snap.title_present = "申请创建租户" in text
        snap.has_tree = bool(re.search(r"\(\s*ZH[\w_]*\d+\s*\)", text))
        snap.has_admin = "租户管理员" in text
        snap.has_phone = "手机号" in text
        snap.has_desc = "申请说明" in text
        snap.has_declaration = "确认" in text and ("勾选" in text or "同意" in text)
        snap.has_cancel = "取消" in text or "取 消" in text
        snap.has_submit = "提交" in text or "提 交" in text

        # 提交按钮状态：只读 is_disabled，绝不点击
        try:
            btn = self.page.get_by_role("button", name=re.compile("确认提交|提\\s*交")).last
            snap.submit_disabled = btn.is_disabled() if btn.count() else None
        except Exception:
            snap.submit_disabled = None

        # 租户名称是否只读
        try:
            name_input = self.page.get_by_label(re.compile("租户名称")).first
            snap.tenant_name_readonly = (
                name_input.get_attribute("readonly") is not None
                or name_input.get_attribute("disabled") is not None
            ) if name_input.count() else None
        except Exception:
            snap.tenant_name_readonly = None

        snap.enterprises = self._parse_enterprises(text)
        return snap

    def _parse_enterprises(self, text: str) -> list[dict]:
        """把「企业名(ZH_xxx)」与其后的状态词配对。"""
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        out: list[dict] = []
        for i, ln in enumerate(lines):
            if "ZH_" in ln and "(" in ln:
                tail = lines[i + 1: i + 4]
                states = [w for w in STATUS_WORDS if any(w in t for t in tail)]
                out.append({"label": ln[:70], "states": states})
        return out[:20]

    def _parse_tenants(self) -> tuple[TenantRow, ...]:
        """解析切换租户面板：名称 + 状态词。"""
        try:
            text = self.page.locator("body").inner_text()
        except Exception:
            return ()
        lines = [x.strip() for x in text.splitlines() if x.strip()]
        rows: list[TenantRow] = []
        for i, ln in enumerate(lines):
            if len(ln) < 2 or len(ln) > 40:
                continue
            tail = "\n".join(lines[i + 1: i + 3])
            states = tuple(w for w in STATUS_WORDS if w in tail)
            if states and ln not in STATUS_WORDS:
                rows.append(TenantRow(name=ln, states=states))
        # 去重（同名只留首条）
        seen: set[str] = set()
        uniq = []
        for r in rows:
            if r.name in seen:
                continue
            seen.add(r.name)
            uniq.append(r)
        return tuple(uniq[:20])

    # ---------------- 前置条件 ----------------

    @staticmethod
    def opener_prerequisite(rows: tuple[TenantRow, ...]) -> PrerequisiteResult:
        """切换租户面板是否可用（至少一条记录）。"""
        return PrerequisiteResult(
            satisfied=bool(rows),
            reason="切换租户面板未渲染任何租户记录",
            expected="面板至少包含 1 条租户（含状态标签）",
            actual=f"rows={len(rows)}",
        )

    @staticmethod
    def applying_branch_prerequisite(rows: tuple[TenantRow, ...]) -> PrerequisiteResult:
        """是否存在「申请中」样本（M02-L04 后半段需要）。"""
        applying = [r for r in rows if r.applying]
        return PrerequisiteResult(
            satisfied=bool(applying),
            reason="当前账号没有「申请中」记录的租户",
            expected="切换列表至少 1 条「申请中」记录",
            actual=f"applying={len(applying)}, total={len(rows)}",
        )

    @staticmethod
    def submittable_prerequisite(dialog: DialogSnapshot) -> PrerequisiteResult:
        """是否存在「可提交」企业（已认证且未开通）。"""
        candidates = [
            e for e in dialog.enterprises
            if "已开通" not in e["states"] and "未认证" not in e["states"]
        ]
        return PrerequisiteResult(
            satisfied=bool(candidates),
            reason="当前账号关联的企业中没有「已认证、未开通」样本，无法验证正向提交",
            expected="至少 1 个既非已开通也非未认证的企业",
            actual=f"enterprises={len(dialog.enterprises)}, candidates={len(candidates)}",
        )

    # ---------------- 内部 ----------------

    def _click(self, label: str, wait_ms: int = 0) -> bool:
        for factory in (
            lambda: self.page.get_by_role("menuitem", name=label, exact=True).last,
            lambda: self.page.get_by_text(label, exact=True).last,
        ):
            try:
                loc = factory()
                if loc.count() and loc.is_visible(timeout=2500):
                    loc.click()
                    if wait_ms:
                        self.page.wait_for_timeout(wait_ms)
                    return True
            except Exception:
                continue
        return False

    def reopen_switcher(self) -> tuple[TenantRow, ...]:
        """关闭弹窗后重新打开「切换租户」面板（用于验证取消无残留）。"""
        self.close_dialogs(times=2)
        if not self._click("切换租户", wait_ms=2500):
            raise AssertionError("取消后「切换租户」入口不可达")
        self._tenant_rows = self._parse_tenants()
        return self._tenant_rows

    def close_dialogs(self, times: int = 3) -> None:
        for _ in range(times):
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(500)
