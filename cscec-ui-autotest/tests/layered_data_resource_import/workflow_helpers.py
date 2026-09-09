"""Shared workflow helpers to reduce boilerplate in layered data resource import tests.

封装「下载模板 → 读表头 → 按 row_builder 构造唯一 xlsx → 上传 → 校验」这段高频样板。
调用方负责先 ``open_mXX_import_dialog()``，随后自行断言结果并 ``close_import_dialog()``。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from tests.dataresources.import_workbooks import create_workbook_from_template, read_first_sheet_headers


def build_upload_validate(
    page,
    tmp_path: Path,
    run_id: str,
    row_builder: Callable[[list[str]], Any],
) -> tuple[list[str], Any]:
    """下载模板→读表头→按 ``row_builder(headers)`` 构造唯一 xlsx→上传→校验。

    参数:
        page: LayeredImportPage 实例（需已打开目标导入弹窗）。
        tmp_path: pytest tmp_path。
        run_id: 唯一运行 token，用于生成 xlsx 文件名。
        row_builder: 接收表头，返回单行 dict 或多行 list[dict]。

    返回:
        (headers, row_values)，供需要复用行值/表头的用例使用。
    """
    template_file = page.download_template(tmp_path)
    headers = read_first_sheet_headers(template_file)
    row_values = row_builder(headers)
    import_file = create_workbook_from_template(template_file, tmp_path / f"{run_id}.xlsx", headers, row_values)
    page.upload_file(import_file)
    page.click_validate_table()
    return headers, row_values
