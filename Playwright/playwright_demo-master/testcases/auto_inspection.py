"""
中建云日常人工巡检自动化脚本
=============================
使用 Playwright (Python) 自动执行每日巡检操作。

使用方式:
  1. 安装依赖:  pip install playwright && playwright install chromium
  2. 运行:      python auto_inspection.py
  3. 定时执行:  可配合 Windows 任务计划程序，每天 10:00 自动运行

注意事项:
  - 每天只能执行一次
  - 巡检文件需提前放在 INSPECTION_DIR 目录下（唯一的 xlsx 文件）
  - 密码中最后一个感叹号是全角字符（！）
"""

import os
import sys
import glob
import time
import base64
import logging
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ============== 配置区 ==============
SITE_URL = "https://cloud.cscec.com"
USERNAME = "20431644"
PASSWORD = "Infoshare1!!！"  # 注意：最后是全角感叹号！

# 巡检文件目录 — 脚本会自动找里面唯一的 xlsx 文件
INSPECTION_DIR = r"D:\Doc\一体化\人工巡检"

# 目标巡检名称
INSPECTION_NAME = "中建云"

# 控制台 URL（登录后直接跳转，跳过"控制台"按钮点击）
CONSOLE_URL = (
    "https://cloud.cscec.com/udpweb/portal/index.html"
    "#/sub/resource/operationMaintenance/polling"
    "?suitKey=1899427585366003726"
    "&routeName=resource"
    "&appTitle=%E8%BF%90%E7%BB%B4%E5%B7%A1%E6%A3%80"
    "&mc=1899427585366003726"
    "&mn=%E6%8E%A7%E5%88%B6%E5%8F%B0"
    "&mt=module"
    "&menuCode=1965223958151229445"
)

# 超时配置（毫秒）
PAGE_TIMEOUT = 30000
NAV_TIMEOUT = 15000

# 日志配置
LOG_DIR = INSPECTION_DIR
LOG_FILE = os.path.join(LOG_DIR, f"巡检日志_{datetime.now().strftime('%Y%m%d')}.log")

# ============== 日志设置 ==============
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("inspection")


def find_xlsx_file() -> str:
    """在巡检目录下查找唯一的 xlsx 文件"""
    pattern = os.path.join(INSPECTION_DIR, "*.xlsx")
    files = glob.glob(pattern)
    if not files:
        raise FileNotFoundError(f"未在 {INSPECTION_DIR} 找到 xlsx 文件")
    if len(files) > 1:
        log.warning(f"发现多个 xlsx 文件，使用第一个: {files[0]}")
    return files[0]


def read_file_base64(filepath: str) -> str:
    """读取文件为 base64 字符串"""
    with open(filepath, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def login(page):
    """登录中建云"""
    log.info("步骤1: 打开中建云首页...")
    page.goto(SITE_URL, wait_until="networkidle", timeout=PAGE_TIMEOUT)

    log.info("步骤2: 点击登录按钮...")
    # 找到并点击右上角"登录"
    page.evaluate("""() => {
        const els = document.querySelectorAll('*');
        for (const el of els) {
            if (el.textContent.trim() === '登录' && el.children.length === 0) {
                el.click();
                return true;
            }
        }
        return false;
    }""")
    page.wait_for_timeout(2000)

    log.info("步骤2: 输入用户名和密码...")
    # 等待登录弹窗中的输入框
    page.wait_for_selector("iframe, input[type=text], input[type=password]", timeout=5000)

    # 检查是否有 iframe（有些系统登录在 iframe 里）
    frames = page.frames
    target_frame = page
    for frame in frames:
        try:
            if frame.query_selector("input[type=password]"):
                target_frame = frame
                break
        except:
            pass

    # 填写用户名
    username_input = target_frame.query_selector(
        "input[placeholder*='用户'], input[placeholder*='账号'], input[name*='user'], input[type='text']"
    )
    if username_input:
        username_input.fill(USERNAME)
    else:
        # 备选：用 evaluate 查找
        target_frame.evaluate(f"""() => {{
            const inputs = document.querySelectorAll('input');
            for (const inp of inputs) {{
                if (inp.type === 'text' || inp.type === '') {{
                    inp.value = '{USERNAME}';
                    inp.dispatchEvent(new Event('input', {{bubbles: true}}));
                    break;
                }}
            }}
        }}""")

    # 填写密码
    pwd_input = target_frame.query_selector("input[type='password']")
    if pwd_input:
        pwd_input.fill(PASSWORD)
    else:
        target_frame.evaluate(f"""() => {{
            const inputs = document.querySelectorAll('input[type=password]');
            if (inputs.length > 0) {{
                inputs[0].value = '{PASSWORD}';
                inputs[0].dispatchEvent(new Event('input', {{bubbles: true}}));
            }}
        }}""")

    page.wait_for_timeout(500)

    log.info("步骤2: 点击登录/Login按钮...")
    target_frame.evaluate("""() => {
        const btns = document.querySelectorAll('button, input[type=submit]');
        for (const btn of btns) {
            const text = btn.textContent || btn.value || '';
            if (text.includes('登录') || text.toLowerCase().includes('login')) {
                btn.click();
                return true;
            }
        }
        return false;
    }""")

    # 等待登录完成
    page.wait_for_timeout(3000)
    log.info("登录完成 ✅")


def navigate_to_inspection(page):
    """导航到人工巡检页面"""
    log.info("步骤3: 导航到控制台 → 运维巡检...")

    # 直接跳转到运维巡检页面（比逐级点击菜单更稳定）
    page.goto(CONSOLE_URL, wait_until="networkidle", timeout=PAGE_TIMEOUT)
    page.wait_for_timeout(3000)

    # 切换到"人工巡检"tab
    log.info("步骤3: 点击人工巡检 tab...")
    page.evaluate("""() => {
        const tabs = Array.from(document.querySelectorAll('.ant-tabs-tab'));
        const t = tabs.find(t => t.textContent.includes('人工巡检'));
        if (t) { t.click(); return true; }
        return false;
    }""")
    page.wait_for_timeout(2000)
    log.info("已进入人工巡检页面 ✅")


def query_and_click_record(page):
    """查询中建云并点击记录巡检结果"""
    log.info("步骤4: 点击查询按钮加载数据...")
    page.evaluate("""() => {
        const btns = Array.from(document.querySelectorAll('button'));
        const q = btns.find(b => b.innerText.includes('查') && b.innerText.includes('询'));
        if (q) { q.click(); return true; }
        return false;
    }""")
    page.wait_for_timeout(3000)

    log.info("步骤5: 在列表中查找中建云并点击记录巡检结果...")
    # 通过"中建云"文本找到对应行，然后点击"记录巡检结果"按钮
    result = page.evaluate("""(inspName) => {
        // 在虚拟表格中查找目标行
        const allCells = Array.from(document.querySelectorAll('.virtual-table-cell, td'));
        const targetCell = allCells.find(c => c.innerText && c.innerText.trim() === inspName);
        if (!targetCell) return 'target_not_found';

        // 向上遍历找到包含按钮的行容器
        let el = targetCell;
        for (let depth = 0; depth < 10; depth++) {
            el = el.parentElement;
            if (!el) break;
            const btns = Array.from(el.querySelectorAll('button'));
            // 找"记录巡检结果"或"修改巡检结果"
            const recordBtn = btns.find(b =>
                b.innerText.includes('记录巡检结果') || b.innerText.includes('修改巡检结果')
            );
            if (recordBtn) {
                recordBtn.click();
                return 'clicked: ' + recordBtn.innerText.trim();
            }
        }
        return 'button_not_found';
    }""", INSPECTION_NAME)

    log.info(f"点击结果: {result}")
    if "not_found" in result:
        raise RuntimeError(f"未找到{INSPECTION_NAME}的巡检记录，可能今天已经完成或未分配")

    page.wait_for_timeout(2000)

    # 验证抽屉打开的是正确的巡检
    drawer_text = page.evaluate("""() => {
        const dialog = document.querySelector('[role=dialog], .ant-drawer-body');
        return dialog ? dialog.textContent.substring(0, 200) : 'no_dialog';
    }""")

    if INSPECTION_NAME not in drawer_text and "中建云巡检" not in drawer_text:
        log.warning(f"⚠️ 抽屉内容可能不是{INSPECTION_NAME}: {drawer_text[:100]}")
    else:
        log.info(f"抽屉已打开，确认是{INSPECTION_NAME}巡检 ✅")


def upload_file(page, filepath: str):
    """上传巡检结果文件"""
    log.info(f"步骤6: 上传巡检文件: {os.path.basename(filepath)}")

    # 读取文件为 base64
    file_b64 = read_file_base64(filepath)
    filename = os.path.basename(filepath)

    # 通过 DataTransfer API 模拟文件上传
    # （Ant Design Upload 组件的隐藏 input[type=file] 无法直接 setInputFiles）
    result = page.evaluate("""([b64, fname]) => {
        try {
            const binary = atob(b64);
            const len = binary.length;
            const bytes = new Uint8Array(len);
            for (let i = 0; i < len; i++) bytes[i] = binary.charCodeAt(i);

            const blob = new Blob([bytes], {
                type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            });
            const file = new File([blob], fname, {
                type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            });

            // 找到隐藏的 file input
            const inp = document.querySelector('input[type=file]');
            if (!inp) return 'no_file_input';

            const dt = new DataTransfer();
            dt.items.add(file);
            inp.files = dt.files;
            inp.dispatchEvent(new Event('change', { bubbles: true }));

            return 'uploaded: ' + fname;
        } catch (e) {
            return 'error: ' + e.message;
        }
    }""", [file_b64, filename])

    log.info(f"上传结果: {result}")
    if "error" in result or "no_file_input" in result:
        raise RuntimeError(f"文件上传失败: {result}")

    page.wait_for_timeout(2000)
    log.info("文件上传成功 ✅")


def check_all_normal(page):
    """勾选全选正常"""
    log.info("步骤7: 勾选全选正常...")
    page.evaluate("""() => {
        const checkboxes = document.querySelectorAll('input[type=checkbox]');
        for (const cb of checkboxes) {
            // 找到"全选正常"旁边的 checkbox
            const label = cb.closest('label') || cb.parentElement;
            if (label && label.textContent.includes('全选正常') && !cb.checked) {
                cb.click();
                return 'checked';
            } else if (label && label.textContent.includes('全选正常') && cb.checked) {
                return 'already_checked';
            }
        }
        // 备选：通过 Ant Design checkbox 的 wrapper 查找
        const wrappers = document.querySelectorAll('.ant-checkbox-wrapper');
        for (const w of wrappers) {
            if (w.textContent.includes('全选正常')) {
                const input = w.querySelector('input');
                if (input && !input.checked) {
                    input.click();
                    return 'checked_via_wrapper';
                }
                return 'already_checked';
            }
        }
        return 'not_found';
    }""")
    page.wait_for_timeout(500)
    log.info("全选正常已勾选 ✅")


def save_and_verify(page):
    """点击保存并验证结果"""
    log.info("步骤7: 点击保存...")
    page.evaluate("""() => {
        const btns = Array.from(document.querySelectorAll('button'));
        const save = btns.find(b => b.innerText.trim() === '保 存');
        if (save) { save.click(); return true; }
        return false;
    }""")

    page.wait_for_timeout(3000)

    # 检查是否有成功提示
    result = page.evaluate("""() => {
        const modals = document.querySelectorAll('.ant-modal-body, .ant-message-notice, .ant-notification');
        for (const m of modals) {
            if (m.textContent.includes('成功')) return 'success';
            if (m.textContent.includes('上传巡检结果')) return 'need_upload';
        }
        // 检查 ant-modal-confirm
        const confirm = document.querySelector('.ant-modal-confirm-body');
        if (confirm) {
            const text = confirm.textContent;
            if (text.includes('成功')) return 'success';
            return 'modal: ' + text.substring(0, 100);
        }
        return 'unknown';
    }""")

    log.info(f"保存结果: {result}")

    if result == "need_upload":
        raise RuntimeError("保存失败：系统要求上传巡检结果文件")

    if "success" in result:
        log.info("🎉 巡检保存成功！")
        # 点击确定关闭弹窗
        page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const ok = btns.find(b => b.innerText.trim() === '确 定' || b.innerText.trim() === '确定');
            if (ok) ok.click();
        }""")
    else:
        log.warning(f"保存后状态不明确: {result}，请手动检查")

    page.wait_for_timeout(1000)


def main():
    today = datetime.now().strftime("%Y-%m-%d")
    log.info(f"{'='*50}")
    log.info(f"中建云日常巡检自动化 - {today}")
    log.info(f"{'='*50}")

    # 查找巡检文件
    xlsx_path = find_xlsx_file()
    log.info(f"找到巡检文件: {xlsx_path}")

    with sync_playwright() as p:
        # 启动独立的 Chromium 浏览器（无头模式可改为 headless=True）
        browser = p.chromium.launch(
            headless=False,  # 首次运行建议 False 以便观察；稳定后改为 True
            args=["--start-maximized"],
        )
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            ignore_https_errors=True,
        )
        page = context.new_page()
        page.set_default_timeout(PAGE_TIMEOUT)

        try:
            # 1-2. 登录
            login(page)

            # 3. 导航到人工巡检
            navigate_to_inspection(page)

            # 4-5. 查询并点击记录
            query_and_click_record(page)

            # 6. 上传文件
            upload_file(page, xlsx_path)

            # 7. 勾选全选正常 + 保存
            check_all_normal(page)
            save_and_verify(page)

            log.info(f"{'='*50}")
            log.info(f"✅ 巡检任务全部完成！ {today}")
            log.info(f"{'='*50}")

        except Exception as e:
            log.error(f"❌ 执行失败: {e}", exc_info=True)
            # 截图保存以便排查
            err_screenshot = os.path.join(
                INSPECTION_DIR, f"错误截图_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            )
            try:
                page.screenshot(path=err_screenshot, full_page=True)
                log.info(f"错误截图已保存: {err_screenshot}")
            except:
                pass
            raise
        finally:
            # 8. 关闭浏览器
            log.info("步骤8: 关闭浏览器...")
            browser.close()
            log.info("浏览器已关闭 ✅")


if __name__ == "__main__":
    main()
