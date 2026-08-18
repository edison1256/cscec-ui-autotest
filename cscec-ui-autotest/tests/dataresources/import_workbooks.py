"""Helpers for data resource import workbook tests."""

from __future__ import annotations

import os
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree
from xml.sax.saxutils import escape

from config.settings import settings


_MAIN_NS = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _current_env() -> str:
    return (os.getenv("ENV") or settings.ENV or "uat").lower()


# 环境参考值：UAT 与 PRE 库数据不同，动态构造器需按环境取合法的域/系统/分层/已存在实体。
# PRE 值来源：2026-08-18 实测 irp-pre.cscec.com（数据资源列表 + 数据分层设置树 + test0001 编辑表单）。
# 实测结论：PRE 的「人力资源」域为空、「中国建筑科技管理系统」系统不存在；
# PRE 实际有「测试test」域 +「测试test123」系统 + 实体「test0001」（与 UAT 同源），
# 另有「建造一体化」域 +「数字建造生产线」系统（生产类数据）。
# test0001 分层归属（编辑表单实测）：一级应用域=测试test，L1=test001，L2=test002，L3=test003。
_UAT_REFS = {
    "layer_app_domain": "测试test260812",
    "app_domain": "测试test",
    "app_system": "测试test123",
    "l1": "测试使用",
    "l2": "测试",
    "l3": "主线程1",
    "mismatch_domain": "测试2",
    "existing_table_en": "shujuzichanceSHI",
}
_PRE_REFS = {
    "layer_app_domain": "测试test",        # PRE 无「测试test260812」，M02 分层域用「测试test」
    "app_domain": "测试test",              # PRE「人力资源」域为空，改用有实体的「测试test」
    "app_system": "测试test123",           # PRE「中国建筑科技管理系统」不存在，改用「测试test123」
    "l1": "test001",                       # 实测 test0001 编辑表单 L1
    "l2": "test002",                       # 实测 test0001 编辑表单 L2
    "l3": "test003",                       # 实测 test0001 编辑表单 L3
    "mismatch_domain": "建造一体化",       # PRE 真实域，测试test123 不属其
    "existing_table_en": "test0001",       # 实测存在（测试test/测试test123 下）
}
_REFS = _PRE_REFS if _current_env() == "pre" else _UAT_REFS

_VALID_APP_DOMAIN = _REFS["app_domain"]
_VALID_LAYER_APP_DOMAIN = _REFS["layer_app_domain"]
_MISMATCH_APP_DOMAIN = _REFS["mismatch_domain"]
_VALID_APP_SYSTEM = _REFS["app_system"]
_VALID_EXISTING_TABLE_ENGLISH_NAME = _REFS["existing_table_en"]
_VALID_L1 = _REFS["l1"]
_VALID_L2 = _REFS["l2"]
_VALID_L3 = _REFS["l3"]


def read_first_sheet_headers(workbook_path: Path) -> list[str]:
    """Read the first non-empty row from the first worksheet as headers."""
    with zipfile.ZipFile(workbook_path) as archive:
        shared_strings = _read_shared_strings(archive)
        worksheet = ElementTree.fromstring(archive.read("xl/worksheets/sheet1.xml"))

    for row in worksheet.findall(".//main:sheetData/main:row", _MAIN_NS):
        values = [_cell_text(cell, shared_strings).strip() for cell in row.findall("main:c", _MAIN_NS)]
        headers = [value for value in values if value]
        if headers:
            return headers

    raise AssertionError(f"模板中未读取到表头: {workbook_path}")


def create_workbook_from_headers(
    tmp_path: Path,
    filename: str,
    headers: list[str],
    row_values: dict[str, str] | list[dict[str, str]],
) -> Path:
    """Create a minimal xlsx with template headers and one or more data rows."""
    path = tmp_path / filename
    rows = row_values if isinstance(row_values, list) else [row_values]
    data_rows = [[row.get(header, "") for header in headers] for row in rows]
    sheet_xml = _worksheet_xml([headers, *data_rows])
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
          xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="Sheet1" sheetId="1" r:id="rId1"/>
  </sheets>
</workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>""",
        )
        archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return path


def create_m03_column_mismatch_workbook(tmp_path: Path, table_english_name: str) -> Path:
    """Create an M03 workbook whose header intentionally mismatches the template."""
    headers = [
        "一级应用域名称",
        "应用系统名称",
        "L1",
        "L2",
        "L3",
        "表中文名称",
        "表英文名称_错误",
        "表描述",
        "存储周期",
        "系统项目组",
    ]
    row_values = {
        "一级应用域名称": "数字辅助决策",
        "应用系统名称": "信创OA系统",
        "L1": "测试L1",
        "L2": "测试L2",
        "L3": "测试L3",
        "表中文名称": "自动化列名不符测试表",
        "表英文名称_错误": table_english_name,
        "表描述": "自动化列名不符负向校验",
        "存储周期": "永久",
        "系统项目组": "自动化测试组",
    }
    return create_workbook_from_headers(
        tmp_path,
        f"M03_column_mismatch_{table_english_name}.xlsx",
        headers,
        row_values,
    )


def m02_unique_layer_row(headers: list[str], run_id: str) -> dict[str, str]:
    """Build one unique M02 row that should not conflict with prior imports."""
    token = _safe_token(run_id)
    row = _default_row(headers)
    row.update(
        {
            "一级应用域名称": _VALID_LAYER_APP_DOMAIN,
            "L1": f"auto_l1_{token}",
            "L1定义": f"auto_l1_def_{token}",
            "L2": f"auto_l2_{token}",
            "L2定义": f"auto_l2_def_{token}",
            "L3": f"auto_l3_{token}",
            "L3定义": f"auto_l3_def_{token}",
        }
    )
    return row


def m02_duplicate_layer_rows(headers: list[str], run_id: str) -> list[dict[str, str]]:
    """Build two M02 rows with the same unique business key for in-file duplicate checks."""
    first = m02_unique_layer_row(headers, run_id)
    second = dict(first)
    second["L3定义"] = f"{first['L3定义']}_second"
    return [first, second]


def m02_diff_l1_same_l2_pass_rows(headers: list[str], run_id: str) -> list[dict[str, str]]:
    """Build two M02 rows sharing the same L2 name under different L1 (should NOT be duplicate).

    对应大纲「不同一级应用域/不同 L1 下出现相同 L2，期望允许通过校验」——
    重复判定键为完整路径（域+L1+L2+L3 名称），仅 L2 同名不构成重复。
    """
    token = _safe_token(run_id)
    domain = _VALID_LAYER_APP_DOMAIN
    shared_l2 = f"auto_shared_l2_{token}"

    def _row(l1: str) -> dict[str, str]:
        row = _default_row(headers)
        row.update(
            {
                "一级应用域名称": domain,
                "L1": l1,
                "L1定义": f"{l1}_def",
                "L2": shared_l2,
                "L2定义": f"{shared_l2}_def",
                "L3": f"auto_l3_{token}_{l1}",
                "L3定义": f"auto_l3_{token}_{l1}_def",
            }
        )
        return row

    return [_row(f"auto_l1_a_{token}"), _row(f"auto_l1_b_{token}")]


def m03_missing_app_domain_row(headers: list[str], table_english_name: str) -> dict[str, str]:
    """Build one M03 row that should fail business validation in the UI."""
    base = m03_valid_like_row(headers, table_english_name)
    base["一级应用域名称"] = "自动化不存在应用域"
    base["一级应用域"] = "自动化不存在应用域"
    return base


def m03_missing_app_system_row(headers: list[str], table_english_name: str) -> dict[str, str]:
    """Build one M03 row with a missing app system name."""
    base = m03_valid_like_row(headers, table_english_name)
    base["应用系统名称"] = "自动化不存在系统"
    base["应用系统"] = "自动化不存在系统"
    return base


def m03_app_domain_system_mismatch_row(headers: list[str], table_english_name: str) -> dict[str, str]:
    """Build one M03 row where app domain and app system should not correspond."""
    base = m03_valid_like_row(headers, table_english_name)
    base["一级应用域名称"] = _MISMATCH_APP_DOMAIN
    base["一级应用域"] = _MISMATCH_APP_DOMAIN
    base["应用系统名称"] = _VALID_APP_SYSTEM
    base["应用系统"] = _VALID_APP_SYSTEM
    return base


def m03_missing_layer_row(headers: list[str], table_english_name: str) -> dict[str, str]:
    """Build one M03 row with a missing layer value."""
    base = m03_valid_like_row(headers, table_english_name)
    base["L2"] = "自动化不存在L2"
    return base


def m03_missing_required_field_row(headers: list[str], table_english_name: str) -> dict[str, str]:
    """Build one M03 row with a required field left empty."""
    base = m03_valid_like_row(headers, table_english_name)
    base["表英文名称"] = ""
    base["表英文名"] = ""
    return base


def m03_multiple_error_rows(headers: list[str], table_english_name: str) -> list[dict[str, str]]:
    """Build two M03 rows that should both appear in visible validation errors."""
    missing_domain = m03_missing_app_domain_row(headers, f"{table_english_name}_domain")
    missing_system = m03_missing_app_system_row(headers, f"{table_english_name}_system")
    return [missing_domain, missing_system]


def m03_duplicate_entity_rows(headers: list[str], table_english_name: str) -> list[dict[str, str]]:
    """Build two M03 rows with the same entity key and different payload for duplicate-mode checks."""
    first = m03_valid_like_row(headers, table_english_name)
    second = dict(first)
    second["表中文名称"] = f"{first.get('表中文名称', '自动化实体')}覆盖"
    second["表中文名"] = f"{first.get('表中文名', '自动化实体')}覆盖"
    second["表描述"] = f"{first.get('表描述', '自动化描述')} second"
    return [first, second]


def m03_valid_pre_import_row(headers: list[str], table_english_name: str) -> dict[str, str]:
    """Build one M03 row that should pass validation without clicking final import."""
    base = m03_valid_like_row(headers, table_english_name)
    base["表中文名称"] = f"自动化导入前校验{table_english_name[-10:]}"
    base["表中文名"] = f"自动化导入前校验{table_english_name[-10:]}"
    base["表描述"] = "自动化导入前校验通过，不点击最终导入"
    return base


def m03_many_valid_rows(headers: list[str], table_english_name: str, count: int) -> list[dict[str, str]]:
    """Build ``count`` valid M03 rows for representative medium/large-file capacity checks.

    每条行使用唯一表英文名后缀，确保互不重复、可整体导入。用于 M5「较大文件导入完成且列表可查询」。
    """
    rows: list[dict[str, str]] = []
    for i in range(count):
        row = m03_valid_like_row(headers, f"{table_english_name}_{i}")
        row["表中文名称"] = f"容量测试表{i}"
        row["表中文名"] = f"容量测试表{i}"
        rows.append(row)
    return rows


def m03_valid_like_row(headers: list[str], table_english_name: str) -> dict[str, str]:
    """Build one M03 row from known UAT fixture-like values without clicking final import."""
    base = _default_row(headers)
    base.update(
        {
            "一级应用域编号": "",
            "一级应用域名称": _VALID_APP_DOMAIN,
            "一级应用域": _VALID_APP_DOMAIN,
            "应用系统编码": "",
            "应用系统名称": _VALID_APP_SYSTEM,
            "应用系统": _VALID_APP_SYSTEM,
            "L1": _VALID_L1,
            "L2": _VALID_L2,
            "L3": _VALID_L3,
            "表中文名称": "自动化业务错误测试表",
            "表中文名": "自动化业务错误测试表",
            "表英文名称": table_english_name,
            "表英文名": table_english_name,
            "表描述": "自动化业务错误负向校验",
            "存储周期": "永久",
            "存储类型": "永久",
            "业务类型": "预发项目组",
            "系统环境类型": "测试环境",
            "数据责任部门": "自动化测试部",
            "系统项目组": "自动化测试组",
        }
    )
    return base


def m04_invalid_attribute_row(headers: list[str], table_english_name: str, field_english_name: str) -> dict[str, str]:
    """Build one M04 row that should fail with visible row-level errors."""
    row = _default_row(headers)
    for header in headers:
        if header == "一级应用域编号":
            row[header] = ""
        elif header in {"一级应用域名称", "一级应用域"}:
            row[header] = "自动化不存在应用域"
        elif header == "应用系统编码":
            row[header] = ""
        elif header in {"应用系统名称", "应用系统"}:
            row[header] = "自动化不存在系统"
        elif header in {"L1", "L2", "L3"}:
            row[header] = f"自动化{header}"
        elif header in {"表中文名称", "表中文名"}:
            row[header] = "自动化不存在实体表"
        elif header in {"表英文名称", "表英文名"}:
            row[header] = table_english_name
        elif header in {"字段中文名称", "字段中文名"}:
            row[header] = "自动化错误字段"
        elif header in {"字段英文名称", "字段英文名"}:
            row[header] = field_english_name
        elif "长度" in header:
            row[header] = "32"
        elif "精度" in header:
            row[header] = "0"
        elif header.startswith("是否"):
            row[header] = "错误"
        elif header in {"数据安全类别", "数据分级", "数据分类"}:
            row[header] = "错误"
    return row


def m04_missing_required_field_row(
    headers: list[str],
    table_english_name: str,
    field_english_name: str,
) -> dict[str, str]:
    """Build one M04 row with a required field left empty."""
    row = m04_invalid_attribute_row(headers, table_english_name, field_english_name)
    if "一级应用域名称" in row:
        row["一级应用域名称"] = ""
    if "一级应用域" in row:
        row["一级应用域"] = ""
    return row


def m04_missing_locator_row(
    headers: list[str],
    table_english_name: str,
    field_english_name: str,
) -> dict[str, str]:
    """Build one M04 row whose entity locator does not exist."""
    row = m04_valid_like_row(headers, table_english_name, field_english_name)
    row["L1"] = "自动化不存在L1"
    _set_first_existing_key(row, {"表英文名称", "表英文名"}, _VALID_EXISTING_TABLE_ENGLISH_NAME)
    return row


def m04_missing_entity_row(
    headers: list[str],
    table_english_name: str,
    field_english_name: str,
) -> dict[str, str]:
    """Build one M04 row whose table English name does not match an existing entity."""
    return m04_valid_like_row(headers, table_english_name, field_english_name)


def m04_empty_boolean_flags_row(headers: list[str], field_english_name: str) -> dict[str, str]:
    """Build one M04 row with required boolean flags left empty."""
    row = m04_valid_like_row(headers, _VALID_EXISTING_TABLE_ENGLISH_NAME, field_english_name)
    for key in ("是否主键", "是否可空", "是否外键"):
        if key in row:
            row[key] = ""
    return row


def m04_missing_security_classification_row(headers: list[str], field_english_name: str) -> dict[str, str]:
    """Build one M04 row with required data security classification fields left empty."""
    row = m04_valid_like_row(headers, _VALID_EXISTING_TABLE_ENGLISH_NAME, field_english_name)
    for key in ("数据安全分类", "数据安全分级"):
        if key in row:
            row[key] = ""
    return row


def m04_source_system_flag_empty_row(headers: list[str], field_english_name: str) -> dict[str, str]:
    """Build one M04 row where '是否本系统产生的数据' is empty but validation should pass."""
    row = m04_valid_like_row(headers, _VALID_EXISTING_TABLE_ENGLISH_NAME, field_english_name)
    if "是否本系统产生的数据" in row:
        row["是否本系统产生的数据"] = ""
    return row


def m04_source_system_flag_unrestricted_row(headers: list[str], field_english_name: str) -> dict[str, str]:
    """Build one M04 row where '是否本系统产生的数据' is not yes/no but should not block validation."""
    row = m04_valid_like_row(headers, _VALID_EXISTING_TABLE_ENGLISH_NAME, field_english_name)
    if "是否本系统产生的数据" in row:
        row["是否本系统产生的数据"] = "自动化任意值"
    return row


def m04_optional_fields_empty_row(headers: list[str], field_english_name: str) -> dict[str, str]:
    """Build one M04 row with optional fields left empty while required fields remain valid."""
    row = m04_valid_like_row(headers, _VALID_EXISTING_TABLE_ENGLISH_NAME, field_english_name)
    for key in (
        "一级应用域编号",
        "应用系统编码",
        "外键关联信息",
        "是否本系统产生的数据",
        "数据来源系统",
        "数据来源本系统模块",
        "是否国资监管",
        "监管指标项编号",
        "监管指标项名称",
    ):
        if key in row:
            row[key] = ""
    return row


def m04_valid_attribute_row(headers: list[str], field_english_name: str) -> dict[str, str]:
    """Build one M04 row against a known-existing entity that should pass validation and be importable."""
    return m04_valid_like_row(headers, _VALID_EXISTING_TABLE_ENGLISH_NAME, field_english_name)


def m04_missing_field_cn_name_row(headers: list[str], field_english_name: str) -> dict[str, str]:
    """Build one M04 row with 字段中文名称 empty (required field)."""
    row = m04_valid_attribute_row(headers, field_english_name)
    for key in ("字段中文名称", "字段中文名"):
        if key in row:
            row[key] = ""
    return row


def m04_missing_field_en_name_row(headers: list[str], field_english_name: str) -> dict[str, str]:
    """Build one M04 row with 字段英文名称 empty (required field)."""
    row = m04_valid_attribute_row(headers, field_english_name)
    for key in ("字段英文名称", "字段英文名"):
        if key in row:
            row[key] = ""
    return row


def m04_missing_field_definition_row(headers: list[str], field_english_name: str) -> dict[str, str]:
    """Build one M04 row with 字段类型 empty (one of the required definition fields)."""
    row = m04_valid_attribute_row(headers, field_english_name)
    if "字段类型" in row:
        row["字段类型"] = ""
    return row


def m04_boolean_flags_wrong_value_row(headers: list[str], field_english_name: str) -> dict[str, str]:
    """Build one M04 row with 是否主键/是否可空/是否外键 set to a non 是/否 value."""
    row = m04_valid_attribute_row(headers, field_english_name)
    for key in ("是否主键", "是否可空", "是否外键"):
        if key in row:
            row[key] = "错误"
    return row


def m04_locator_mismatch_row(
    headers: list[str],
    table_english_name: str,
    field_english_name: str,
) -> dict[str, str]:
    """Build one M04 row where app domain and app system should not correspond."""
    row = m04_valid_like_row(headers, table_english_name, field_english_name)
    if "一级应用域名称" in row:
        row["一级应用域名称"] = _MISMATCH_APP_DOMAIN
    if "一级应用域" in row:
        row["一级应用域"] = _MISMATCH_APP_DOMAIN
    _set_first_existing_key(row, {"表英文名称", "表英文名"}, _VALID_EXISTING_TABLE_ENGLISH_NAME)
    return row


def m04_valid_like_row(headers: list[str], table_english_name: str, field_english_name: str) -> dict[str, str]:
    """Build one M04 row from known UAT fixture-like values without clicking final import."""
    row = _default_row(headers)
    for header in headers:
        if header == "一级应用域编号":
            row[header] = ""
        elif header in {"一级应用域名称", "一级应用域"}:
            row[header] = _VALID_APP_DOMAIN
        elif header == "应用系统编码":
            row[header] = ""
        elif header in {"应用系统名称", "应用系统"}:
            row[header] = _VALID_APP_SYSTEM
        elif header == "L1":
            row[header] = _VALID_L1
        elif header == "L2":
            row[header] = _VALID_L2
        elif header == "L3":
            row[header] = _VALID_L3
        elif header in {"表中文名称", "表中文名"}:
            row[header] = "自动化不存在实体表"
        elif header in {"表英文名称", "表英文名"}:
            row[header] = table_english_name
        elif header in {"字段中文名称", "字段中文名"}:
            row[header] = "自动化字段"
        elif header in {"字段英文名称", "字段英文名"}:
            row[header] = field_english_name
        elif header == "字段业务规则和含义":
            row[header] = "自动化负向校验"
        elif header == "字段类型":
            row[header] = "varchar"
        elif header == "取值范围":
            row[header] = "文本"
        elif "长度" in header:
            row[header] = "32"
        elif "精度" in header:
            row[header] = "0"
        elif header.startswith("是否"):
            row[header] = "否"
        elif header == "缺省值":
            row[header] = "无"
        elif header == "数据安全分类":
            row[header] = "组织数据"
        elif header == "数据安全分级":
            row[header] = "1"
    return row


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    values = []
    for item in root.findall("main:si", _MAIN_NS):
        texts = [node.text or "" for node in item.findall(".//main:t", _MAIN_NS)]
        values.append("".join(texts))
    return values


def _cell_text(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t")
    if cell_type == "s":
        value = cell.findtext("main:v", default="", namespaces=_MAIN_NS)
        return shared_strings[int(value)] if value else ""
    if cell_type == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(".//main:t", _MAIN_NS))
    return cell.findtext("main:v", default="", namespaces=_MAIN_NS)


def _default_row(headers: list[str]) -> dict[str, str]:
    return {header: _default_value_for_header(header) for header in headers}


def _set_first_existing_key(row: dict[str, str], keys: set[str], value: str) -> None:
    for key in keys:
        if key in row:
            row[key] = value
            return


def _default_value_for_header(header: str) -> str:
    if "编号" in header or "编码" in header:
        return ""
    if "英文" in header:
        return _ascii_token(header)
    if "名称" in header:
        return f"自动化{header}"
    if header.startswith("是否"):
        return "否"
    return "自动化测试"


def _ascii_token(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return normalized or "auto_value"


def _safe_token(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_").lower() or "auto"


def _worksheet_xml(rows: list[list[str]]) -> str:
    row_xml = []
    for row_idx, row in enumerate(rows, start=1):
        cells = []
        for col_idx, value in enumerate(row, start=1):
            ref = f"{_column_name(col_idx)}{row_idx}"
            cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>')
        row_xml.append(f'<row r="{row_idx}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(row_xml)}</sheetData>'
        "</worksheet>"
    )


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name
