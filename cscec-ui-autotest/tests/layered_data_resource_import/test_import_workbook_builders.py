from __future__ import annotations

from tests.dataresources.import_workbooks import (
    m02_duplicate_layer_rows,
    m02_unique_layer_row,
    m03_duplicate_entity_rows,
    m03_valid_like_row,
    m04_missing_security_classification_row,
    m04_optional_fields_empty_row,
)


def test_m02_unique_layer_row_uses_run_id_for_repeatable_positive_import():
    headers = ["一级应用域名称", "L1", "L1定义", "L2", "L2定义", "L3", "L3定义"]

    row = m02_unique_layer_row(headers, "m02_uat_abc123")

    assert row["一级应用域名称"] == "测试test260812"
    assert row["L1"] == "auto_l1_m02_uat_abc123"
    assert row["L2"] == "auto_l2_m02_uat_abc123"
    assert row["L3"] == "auto_l3_m02_uat_abc123"


def test_m02_duplicate_layer_rows_create_controlled_in_file_duplicate():
    headers = ["一级应用域名称", "L1", "L1定义", "L2", "L2定义", "L3", "L3定义"]

    rows = m02_duplicate_layer_rows(headers, "m02_uat_dup")

    assert len(rows) == 2
    assert rows[0]["一级应用域名称"] == rows[1]["一级应用域名称"]
    assert rows[0]["L1"] == rows[1]["L1"]
    assert rows[0]["L2"] == rows[1]["L2"]
    assert rows[0]["L3"] == rows[1]["L3"]
    assert rows[0]["L3定义"] != rows[1]["L3定义"]


def test_m03_duplicate_entity_rows_create_same_business_key_with_different_payload():
    headers = ["一级应用域名称", "应用系统名称", "L1", "L2", "L3", "表中文名称", "表英文名称", "表描述", "存储周期", "系统项目组"]

    rows = m03_duplicate_entity_rows(headers, "table_uat_dup")

    assert len(rows) == 2
    assert rows[0]["表英文名称"] == rows[1]["表英文名称"] == "table_uat_dup"
    assert rows[0]["表中文名称"] != rows[1]["表中文名称"]
    assert rows[0]["表描述"] != rows[1]["表描述"]


def test_m03_valid_like_row_accepts_unique_table_english_name():
    headers = ["一级应用域名称", "应用系统名称", "L1", "L2", "L3", "表中文名称", "表英文名称", "表描述", "存储周期", "系统项目组"]

    row = m03_valid_like_row(headers, "auto_m03_unique")

    assert row["表英文名称"] == "auto_m03_unique"


def test_m04_missing_security_classification_row_keeps_locator_valid():
    headers = ["一级应用域名称", "应用系统名称", "L1", "L2", "L3", "表英文名", "字段英文名", "数据安全分类", "数据安全分级"]

    row = m04_missing_security_classification_row(headers, "field_uat_sec")

    assert row["表英文名"] == "shujuzichanceSHI"
    assert row["字段英文名"] == "field_uat_sec"
    assert row["数据安全分类"] == ""
    assert row["数据安全分级"] == ""


def test_m04_optional_fields_empty_row_keeps_required_values():
    headers = ["一级应用域编号", "一级应用域名称", "应用系统编码", "应用系统名称", "L1", "L2", "L3", "表英文名", "字段英文名", "字段类型", "数据安全分类", "数据安全分级"]

    row = m04_optional_fields_empty_row(headers, "field_uat_optional")

    assert row["一级应用域编号"] == ""
    assert row["应用系统编码"] == ""
    assert row["字段英文名"] == "field_uat_optional"
    assert row["字段类型"]
    assert row["数据安全分类"]
