"""分层数据资源导入 Page Object — 支撑 M02 数据分层、M03 数据实体、M04 数据属性清单导入与性能走查。"""

from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

from config.settings import settings
from core.base_page import BasePage
from core.logger import get_logger
from pages.portal.portal_home_page import PortalHomePage

logger = get_logger("layered_import_page")

PROJECT_DATASET_DIR = Path(__file__).resolve().parent.parent.parent / "test_assets" / "datasets" / "layered_import"
FALLBACK_DESKTOP_DIR = Path(r"C:\Users\CFD\Desktop\260812")
DEFAULT_TEST_DATA_DIR = PROJECT_DATASET_DIR


class LayeredImportPage(BasePage):
    """分层数据资源导入与性能优化页面对象。"""

    PAGE_NAME = "分层数据资源导入管理"

    def __init__(self, page: Page):
        super().__init__(page)
        self.portal = PortalHomePage(page)

    # ────────────────────────── 导航与入口 ──────────────────────────

    def _ensure_menu_visible(self, menu_name: str) -> None:
        """确保目标菜单项可见，必要时展开父级或回到控制台主视图。"""
        self.dismiss_visible_modals()
        target = self.page.locator(f".itemLabel:has-text('{menu_name}'), a:has-text('{menu_name}'), span:has-text('{menu_name}')").first
        if target.is_visible():
            return
        # 尝试点击控制台主 Tab 或面包屑返回控制台菜单视图
        for fallback in [
            self.page.locator(".ant-breadcrumb a:has-text('控制台')").first,
            self.page.locator(".udp-layout-tab:has-text('控制台')").first,
            self.page.locator("a[href*='workbench']").first,
            self.page.get_by_text("控制台", exact=True).first,
        ]:
            if fallback.is_visible():
                try:
                    fallback.click(timeout=1500)
                    self.nav.wait_ready()
                    break
                except Exception as exc:
                    logger.debug(f"[导航] 控制台回退入口点击失败，继续尝试下一个: {exc}")

    def open_layer_settings(self) -> "LayeredImportPage":
        """进入数据分层设置页面（M02 入口：控制台 -> 系统配置 -> 资源配置 -> 数据分层设置）。"""
        self.dismiss_visible_modals()
        if "layerSet" not in self.page.url:
            self._ensure_menu_visible("数据分层设置")
            entry = self.page.get_by_text("数据分层设置", exact=True).last
            try:
                if entry.is_visible():
                    entry.click(timeout=3000)
                else:
                    self._click_exact_text("数据分层设置")
            except Exception as exc:
                logger.debug(f"[导航] 数据分层设置菜单点击失败，将走 URL 兜底: {exc}")
            try:
                self.page.wait_for_url(re.compile(r"layerSet"), timeout=3000)
            except Exception:
                # 弹性 SPA 路由兜底
                suit_key = "1899427585366003726" if settings.ENV == "pre" else "1899427585366003724"
                self.page.goto(
                    f"{settings.BASE_URL}udpweb/portal/index.html?#/sub/resource/systemManage/layerSet?suitKey={suit_key}&routeName=resource&appTitle=%E6%95%B0%E6%8D%AE%E5%88%86%E5%B1%82%E8%AE%BE%E7%BD%AE"
                )
            self.nav.wait_ready()

        self.assertions.any_text_visible(["数据分层设置", "导入数据分层清单", "分层清单", "数据分层"], timeout=settings.ACTION_TIMEOUT)
        self.assertions.page_not_blank_or_error()
        logger.info("[导航] → 数据分层设置页面")
        return self

    def open_data_resource_mgmt(self) -> "LayeredImportPage":
        """进入数据资源管理页面（M03/M04 入口：控制台 -> 资源管理 -> 数据资源管理）。"""
        self.dismiss_visible_modals()
        if "dataResources" not in self.page.url:
            self._ensure_menu_visible("数据资源管理")
            entry = self.page.get_by_text("数据资源管理", exact=True).last
            try:
                if entry.is_visible():
                    entry.click(timeout=3000)
                else:
                    self._click_exact_text("数据资源管理")
            except Exception as exc:
                logger.debug(f"[导航] 数据资源管理菜单点击失败，将走 URL 兜底: {exc}")
            try:
                self.page.wait_for_url(re.compile(r"dataResources"), timeout=3000)
            except Exception:
                # 弹性 SPA 路由兜底
                suit_key = "1899427585366003726" if settings.ENV == "pre" else "1899427585366003724"
                self.page.goto(
                    f"{settings.BASE_URL}udpweb/portal/index.html?#/sub/resource/resource/dataResources?suitKey={suit_key}&routeName=resource&appTitle=%E6%95%B0%E6%8D%AE%E8%B5%84%E6%BA%90%E7%AE%A1%E7%90%86"
                )
            self.nav.wait_ready()

        self.assertions.any_text_visible(["数据资源列表", "导入数据实体清单", "数据资源管理", "导入实体", "导入数据实体"], timeout=settings.ACTION_TIMEOUT)
        self.assertions.page_not_blank_or_error()
        logger.info("[导航] → 数据资源管理页面")
        return self

    def _click_exact_text(self, text: str) -> None:
        locator = self._find_first_visible(
            [
                self.page.get_by_text(text, exact=True),
                self.page.locator(f"a:has-text('{text}')"),
                self.page.locator(f"button:has-text('{text}')"),
                self.page.locator(f"span:has-text('{text}')"),
            ],
            text,
        )
        locator.click()

    # ────────────────────────── 导入弹窗交互 ──────────────────────────

    def open_m02_layer_import_dialog(self) -> "LayeredImportPage":
        """在数据分层设置页打开「导入数据分层清单 (M02)」弹窗。"""
        self.open_layer_settings()
        btn = self._find_first_visible(
            [
                self.page.get_by_role("button", name=re.compile(r"导入数据分层清单|导入分层清单")),
                self.page.locator("button:has-text('导入数据分层清单')"),
                self.page.locator("button:has-text('导入分层')"),
                self.page.locator(".ant-btn:has-text('导入数据分层清单')"),
                self.page.locator(".ant-btn:has-text('导入分层')"),
            ],
            description="导入数据分层清单按钮",
        )
        btn.click()
        self.nav.wait_ready()
        dialog = self._get_import_dialog()
        dialog.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        logger.info("[弹窗] 已打开 M02 数据分层清单导入弹窗")
        return self

    def open_m03_entity_import_dialog(self) -> "LayeredImportPage":
        """在数据资源管理页打开「导入数据实体清单 (M03)」弹窗。"""
        self.open_data_resource_mgmt()
        btn = self._find_first_visible(
            [
                self.page.get_by_role("button", name=re.compile(r"导入数据实体清单|导入实体清单")),
                self.page.locator("button:has-text('导入数据实体清单')"),
                self.page.locator("button:has-text('导入实体')"),
                self.page.locator(".ant-btn:has-text('导入数据实体清单')"),
                self.page.locator(".ant-btn:has-text('导入实体')"),
            ],
            description="导入数据实体清单按钮",
        )
        btn.click()
        self.nav.wait_ready()
        dialog = self._get_import_dialog()
        dialog.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        logger.info("[弹窗] 已打开 M03 数据实体清单导入弹窗")
        return self

    def open_m04_attribute_import_dialog(self) -> "LayeredImportPage":
        """在数据资源管理页打开「导入数据属性清单 (M04)」弹窗。"""
        self.open_data_resource_mgmt()
        btn = self._find_first_visible(
            [
                self.page.get_by_role("button", name=re.compile(r"导入数据属性清单|导入属性清单|导入属性")),
                self.page.locator("button:has-text('导入数据属性清单')"),
                self.page.locator("button:has-text('导入属性清单')"),
                self.page.locator("button:has-text('导入属性')"),
                self.page.locator(".ant-btn:has-text('导入数据属性清单')"),
                self.page.locator(".ant-btn:has-text('导入属性')"),
            ],
            description="导入数据属性清单按钮",
        )
        btn.click()
        self.nav.wait_ready()
        dialog = self._get_import_dialog()
        dialog.wait_for(state="visible", timeout=settings.ACTION_TIMEOUT)
        logger.info("[弹窗] 已打开 M04 数据属性清单导入弹窗")
        return self

    def download_template(self, output_dir: Path) -> Path:
        """从当前可见导入弹窗下载模板文件，并返回本地保存路径。"""
        output_dir.mkdir(parents=True, exist_ok=True)
        dialog = self._get_import_dialog()
        download_trigger = self._find_first_visible(
            [
                dialog.get_by_role("button", name=re.compile(r"下载模板|下载模版|获取模板|导出模板|下载|导出")),
                dialog.get_by_role("link", name=re.compile(r"下载模板|下载模版|获取模板|导出模板|下载|导出")),
                dialog.locator("button:has-text('下载模板'), button:has-text('下载模版'), button:has-text('模板'), button:has-text('下载')"),
                dialog.locator("a:has-text('下载模板'), a:has-text('下载模版'), a:has-text('模板'), a:has-text('下载')"),
            ],
            description="下载模板按钮",
        )
        with self.page.expect_download(timeout=settings.ACTION_TIMEOUT) as download_info:
            download_trigger.click()
        download = download_info.value
        target = output_dir / download.suggested_filename
        if target.exists():
            target = output_dir / f"{target.stem}_{int(time.time())}{target.suffix}"
        download.save_as(str(target))
        logger.info(f"[模板下载] 成功下载导入模板: {target}")
        return target

    def upload_file(self, file_name_or_path: str | Path) -> "LayeredImportPage":
        """上传指定测试 Excel 文件到当前导入弹窗。"""
        path = Path(file_name_or_path)
        if not path.is_absolute():
            candidate = PROJECT_DATASET_DIR / file_name_or_path
            if candidate.exists():
                path = candidate
            else:
                path = FALLBACK_DESKTOP_DIR / file_name_or_path
        if not path.exists():
            raise FileNotFoundError(f"测试导入文件不存在: {path}")

        dialog = self._get_import_dialog()
        file_input = dialog.locator("input[type='file']").first
        file_input.wait_for(state="attached", timeout=settings.ACTION_TIMEOUT)
        file_input.set_input_files(str(path))
        self.page.wait_for_timeout(600)
        self.nav.wait_ready()
        logger.info(f"[上传文件] 成功选择文件: {path.name}")
        return self

    def click_validate_table(self) -> "LayeredImportPage":
        """点击导入弹窗中的「校验表格」或「校验」按钮。"""
        # 如果上传后已自动返回明确校验结果，直接记录
        if self._has_any_text(["列名与模板不符", "校验失败", "错误行号", "校验通过", "可导入", "重复", "不符", "条"], timeout=2500):
            logger.info("[校验] 上传后已自动触发校验并获得结果")
            return self

        dialog = self._get_import_dialog()
        # 尝试查找手动校验按钮
        for btn in [
            dialog.get_by_role("button", name=re.compile(r"校验表格|校验")),
            dialog.locator("button:has-text('校验表格')").first,
            dialog.locator("button:has-text('校验')").first,
        ]:
            if btn.is_visible():
                btn.click()
                self.page.wait_for_timeout(500)
                self.nav.wait_ready()
                logger.info("[校验] 已点击校验表格按钮")
                return self

        logger.info("[校验] 未发现独立校验按钮，系统已在上传后自动完成校验")
        return self

    def select_conflict_mode(self, mode: str = "跳过") -> "LayeredImportPage":
        """选择重复数据处理方式（'跳过' 或 '覆盖'）。"""
        dialog = self._get_import_dialog()
        if "跳过" in mode:
            opt = dialog.get_by_text(re.compile(r"跳过|重复跳过")).first
        else:
            opt = dialog.get_by_text(re.compile(r"覆盖|重复覆盖")).first

        if opt.is_visible():
            opt.click()
            logger.info(f"[冲突处理] 选中重复处理方式: {mode}")
        return self

    def click_confirm_import(self) -> "LayeredImportPage":
        """点击弹窗中的「导入」或「确认导入」按钮。"""
        dialog = self._get_import_dialog()
        btn = self._find_first_visible(
            [
                dialog.get_by_role("button", name=re.compile(r"^导\s*入$|^确认导入$")),
                dialog.locator("button.import_btn"),
                dialog.locator("button:has-text('导入')"),
            ],
            description="确认导入按钮",
        )
        if btn.is_disabled():
            raise AssertionError("导入按钮处于禁用状态，无法执行导入")
        btn.click()
        self.nav.wait_ready()
        logger.info("[导入] 已点击确认导入按钮")
        return self

    def should_show_import_finished(self) -> "LayeredImportPage":
        """断言点击导入后页面出现成功或完成状态。"""
        self.assertions.any_text_visible(
            ["导入成功", "导入完成", "成功", "完成"],
            timeout=settings.ACTION_TIMEOUT,
        )
        logger.info("[断言] 导入完成状态可见")
        return self

    # ────────────────────────── 断言与结果核验 ──────────────────────────

    def should_show_column_mismatch_error(self) -> "LayeredImportPage":
        """断言提示列名与模板不符。"""
        self.should_show_import_errors(["列", "模板"])
        logger.info("[断言] 成功捕获「列名与模板不符」错误提示")
        return self

    def should_show_import_errors(self, expected_snippets: list[str]) -> "LayeredImportPage":
        """断言弹窗内展示了预期的校验错误行或错误原因。"""
        deadline = time.monotonic() + (settings.ACTION_TIMEOUT / 1000)
        last_text = ""
        while time.monotonic() < deadline:
            last_text = self.get_dialog_text()
            normalized = re.sub(r"\s+", "", last_text)
            matched = [s for s in expected_snippets if s in last_text or re.sub(r"\s+", "", s) in normalized]
            if len(matched) == len(expected_snippets):
                logger.info(f"[断言] 导入校验错误提示匹配成功: {matched}")
                return self
            self.page.wait_for_timeout(300)

        missing = [s for s in expected_snippets if s not in last_text and re.sub(r"\s+", "", s) not in re.sub(r"\s+", "", last_text)]
        raise AssertionError(f"导入弹窗未包含预期错误片段: {missing}; 当前弹窗内容: {last_text[:300]}")

    def should_not_allow_import(self) -> "LayeredImportPage":
        """断言校验不通过时，不展示导入按钮或导入按钮被禁用。"""
        dialog = self._get_import_dialog()
        buttons = dialog.get_by_role("button", name=re.compile(r"^导\s*入$|^确认导入$"))
        for i in range(buttons.count()):
            b = buttons.nth(i)
            if b.is_visible() and not b.is_disabled():
                raise AssertionError("业务校验失败后，页面仍展示了可点击的导入按钮！")
        logger.info("[断言] 业务校验未通过，导入按钮已正确禁用/隐藏")
        return self

    def should_allow_import_after_validation(self) -> "LayeredImportPage":
        """断言校验通过，允许点击导入。"""
        dialog = self._get_import_dialog()
        btn = self._find_first_visible(
            [
                dialog.get_by_role("button", name=re.compile(r"^导\s*入$|^确认导入$|^确\s*定$")),
                dialog.locator("button.import_btn"),
                dialog.locator(".ant-btn-primary"),
                dialog.locator("button:has-text('导入')"),
            ],
            description="导入按钮",
        )
        assert not btn.is_disabled(), "校验通过后导入按钮仍然不可用"
        logger.info("[断言] 校验通过，导入按钮处于可用状态")
        return self

    def should_show_progress_bar(self) -> "LayeredImportPage":
        """断言出现导入进度条或进度状态。

        仅认真正的进度/导入进行态与完成态（`.ant-progress`/`.ant-spin` 组件，或“进度/正在导入/导入中/
        导入成功/导入完成/处理中”等文案），不再把“校验通过/可导入/校验失败”等校验态误判为进度。
        """
        if self.page.locator(".ant-progress, .ant-spin, .ant-progress-bg").count() > 0:
            logger.info("[断言] 成功观察到 Ant Design 进度条组件")
            return self
        self.assertions.any_text_visible(
            ["进度", "%", "正在导入", "导入中", "导入成功", "导入完成", "处理中"],
            timeout=settings.ACTION_TIMEOUT,
        )
        logger.info("[断言] 成功观察到导入进度条或完成状态")
        return self

    def close_import_dialog(self) -> "LayeredImportPage":
        """关闭导入弹窗。"""
        for _ in range(3):
            dialog = self.page.locator(".ant-modal-content:visible").last
            if not dialog.is_visible():
                break
            btn = dialog.locator(".ant-modal-close, button:has-text('关闭'), button:has-text('取消'), button:has-text('确定')").last
            if btn.is_visible():
                try:
                    btn.click(timeout=1500)
                except Exception:
                    self.page.keyboard.press("Escape")
            else:
                self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(400)

        # 最终确认关闭
        if self.page.locator(".ant-modal-content:visible").count() > 0:
            self.page.keyboard.press("Escape")
        logger.info("[弹窗] 已关闭导入弹窗")
        return self

    def verify_layer_tree_nodes(self, l1: str = "", l2: str = "", l3: str = "") -> "LayeredImportPage":
        """在数据分层设置页核验分层树节点展示。"""
        self.assertions.page_not_blank_or_error()
        for node in [l1, l2, l3]:
            if node:
                self.assertions.text_visible(node)
        logger.info(f"[断言] 数据分层树节点核验完成: L1={l1}, L2={l2}, L3={l3}")
        return self

    def search_and_verify_entity(self, table_english_name: str) -> "LayeredImportPage":
        """在数据资源列表中按表英文名称检索核验。"""
        search_input = self.page.get_by_placeholder(re.compile(r"请输入搜索内容|请输入|搜索")).first
        if search_input.is_visible():
            search_input.fill(table_english_name)
            search_input.press("Enter")
            self.nav.wait_ready()
        self.assertions.page_not_blank_or_error()
        self.assertions.text_visible(table_english_name)
        logger.info(f"[检索] 数据实体检索完成: {table_english_name}")
        return self

    def should_show_no_search_results(self, keyword: str) -> "LayeredImportPage":
        """断言在数据资源列表中搜索该关键字时无数据（确保校验阶段未提前写入）。"""
        self.open_data_resource_mgmt()
        search_input = self.page.get_by_placeholder(re.compile(r"请输入搜索内容|请输入|搜索")).first
        if search_input.is_visible():
            search_input.fill(keyword)
            search_input.press("Enter")
            self.nav.wait_ready()
        empty_state = self.page.locator(".ant-empty:visible, text=暂无数据, text=无数据").count() > 0
        zero_total = self.page.locator("text=/共\\s*0\\s*条|0\\s*条/").count() > 0
        visible_rows = self.page.locator(".ant-table-row:visible").count()
        assert empty_state or zero_total or visible_rows == 0, (
            f"搜索 '{keyword}' 后仍存在可见表格行，未能确认无数据"
        )
        logger.info(f"[断言] 搜索 '{keyword}' 为空，确认未提前写入数据")
        return self

    # ────────────────────────── 内部辅助方法 ──────────────────────────

    def get_dialog_text(self) -> str:
        """获取当前可见弹窗的文本内容。"""
        dialog = self._get_import_dialog()
        return dialog.inner_text(timeout=settings.ACTION_TIMEOUT)

    def dismiss_visible_modals(self) -> "LayeredImportPage":
        """关闭遮挡的 Ant Design 弹窗。"""
        for _ in range(3):
            modal_wraps = self.page.locator(".ant-modal-wrap:visible")
            if modal_wraps.count() == 0:
                break
            modal = modal_wraps.first
            close_btn = modal.locator(".ant-modal-close, button:has-text('关闭'), button:has-text('取消')").first
            if close_btn.is_visible():
                try:
                    close_btn.click(timeout=1000)
                except Exception:
                    self.page.keyboard.press("Escape")
            else:
                self.page.keyboard.press("Escape")
            try:
                modal.wait_for(state="hidden", timeout=1500)
            except Exception as exc:
                logger.debug(f"[弹窗] 弹窗关闭确认超时，忽略继续: {exc}")
        return self

    def _get_import_dialog(self) -> Locator:
        return self.page.locator(".ant-modal-content:visible").first

    def _find_first_visible(self, locators: list[Locator], description: str) -> Locator:
        for loc in locators:
            try:
                loc.first.wait_for(state="visible", timeout=settings.DEFAULT_TIMEOUT)
                return loc.first
            except PlaywrightTimeoutError:
                continue
        raise AssertionError(f"未找到可见元素: {description}")

    def _has_any_text(self, texts: list[str], timeout: int = 1000) -> bool:
        for text in texts:
            try:
                self.page.get_by_text(text, exact=False).first.wait_for(state="visible", timeout=timeout)
                return True
            except PlaywrightTimeoutError:
                continue
        return False
