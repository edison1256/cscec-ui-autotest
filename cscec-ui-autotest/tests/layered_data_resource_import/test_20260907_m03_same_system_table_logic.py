"""20260907 数据资源导入逻辑优化专项自动化。

需求结论：M03 不再用「应用系统名称 + 表英文名称」作为宽泛重复拦截条件；
同一应用系统下同表英文名，只要业务域/L1/L2/L3 完整定位不同，就应允许校验和导入。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from config.settings import settings
from pages.dataresources.layered_import_page import LayeredImportPage
from tests.dataresources.import_workbooks import (
    create_workbook_from_headers,
    m03_same_system_table_rows,
    m04_same_system_table_attribute_row,
    m04_attribute_template_headers,
    read_first_sheet_headers,
    prod_business_layer_paths,
    valid_m03_app_domain,
    valid_m03_app_system,
)
from tests.layered_data_resource_import.data_provider import import_run_id
from tests.layered_data_resource_import.workflow_helpers import build_upload_validate


OLD_DUPLICATE_ERROR_TEXTS = ["应用系统名称字段值相同", "表英文名称不允许相同", "应用系统名称相同", "表英文名称相同"]
PRE_M03_APP_DOMAIN = "建造一体化"
PRE_M03_APP_SYSTEM = "建造一体化_数字建造_开发平台服务_prd"


def _require_uat_or_pre() -> None:
    if settings.ENV not in {"uat", "pre", "prod"}:
        pytest.skip("20260907 数据资源导入逻辑优化专项当前仅在 UAT/PRE/PROD 执行")


def _m03_context() -> dict[str, str]:
    if settings.ENV == "pre":
        return {"app_domain": PRE_M03_APP_DOMAIN, "app_system": PRE_M03_APP_SYSTEM}
    return {"app_domain": valid_m03_app_domain(), "app_system": valid_m03_app_system()}


def _finalize_import(layered_import_page: LayeredImportPage, reopen_data_resource_mgmt: bool = False) -> None:
    if settings.ENV == "pre":
        layered_import_page.close_import_dialog()
        if reopen_data_resource_mgmt:
            layered_import_page.open_data_resource_mgmt()
        return
    layered_import_page.should_show_import_finished()
    layered_import_page.close_import_dialog()


def _layer_paths(run_id: str, variant: str) -> list[dict[str, str]]:
    if settings.ENV == "prod":
        paths = prod_business_layer_paths(run_id)
        if variant == "diff_l1":
            base = paths[:2]
        elif variant == "diff_l2":
            base = [paths[0], paths[2]]
        elif variant == "diff_l3":
            base = [paths[0], paths[3]]
        else:
            raise ValueError(f"Unsupported variant for prod layer paths: {variant}")
        context = _m03_context()
        return [dict(context, **path) for path in base]
    if settings.ENV == "pre":
        base = {
            "diff_l1": [
                {"l1": "生产线", "l2": "综合管理域", "l3": "收发文管理"},
                {"l1": "市场营销", "l2": "综合管理域", "l3": "客户评级规则"},
            ],
            "diff_l2": [
                {"l1": "经济线", "l2": "公共域", "l3": "财务成本科目"},
                {"l1": "经济线", "l2": "考核域", "l3": "风险金预留管理"},
            ],
            "diff_l3": [
                {"l1": "经济线", "l2": "公共域", "l3": "财务成本科目"},
                {"l1": "经济线", "l2": "公共域", "l3": "分包类型映射合同三级分类"},
            ],
        }[variant]
    else:
        base = {
            "diff_l1": [
                {"l1": "test1", "l2": "test1-2", "l3": "test1-3"},
                {"l1": "test2", "l2": "test1-2", "l3": "test1-3"},
            ],
            "diff_l2": [
                {"l1": "测试", "l2": "测试使用", "l3": "主线程"},
                {"l1": "测试", "l2": "260812L2", "l3": "260812L31"},
            ],
            "diff_l3": [
                {"l1": "测试使用", "l2": "测试", "l3": "主线程1"},
                {"l1": "测试使用", "l2": "测试", "l3": "主线程2"},
            ],
        }[variant]
    context = _m03_context()
    return [dict(context, **path) for path in base]


def _assert_no_old_duplicate_error(dialog_text: str) -> None:
    normalized = "".join(dialog_text.split())
    unexpected = [text for text in OLD_DUPLICATE_ERROR_TEXTS if text in normalized]
    assert not unexpected, f"仍出现旧的同应用系统同表英文名重复拦截提示: {unexpected}; 弹窗内容={dialog_text[:500]}"


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
@pytest.mark.write
class TestM03SameSystemTableLogic20260907:
    """M03 同应用系统同表英文名新重复规则。"""

    @pytest.mark.parametrize("variant", ["diff_l1", "diff_l2", "diff_l3"])
    def test_m03_same_system_same_table_different_business_layer_passes_validation(
        self,
        layered_import_page: LayeredImportPage,
        tmp_path: Path,
        variant: str,
    ):
        """不同 L1/L2/L3 完整定位下，同应用系统同表英文名不再被旧规则拦截。"""
        _require_uat_or_pre()
        run_id = import_run_id(f"m03_same_table_{variant}")
        table_english_name = f"auto_same_table_{variant}_{run_id[-8:]}"
        layer_paths = _layer_paths(run_id, variant)

        layered_import_page.open_m03_entity_import_dialog()
        build_upload_validate(
            layered_import_page,
            tmp_path,
            run_id,
            lambda headers: m03_same_system_table_rows(headers, table_english_name, layer_paths),
        )
        dialog_text = layered_import_page.get_dialog_text()
        _assert_no_old_duplicate_error(dialog_text)
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.close_import_dialog()

    def test_m03_same_system_same_table_different_l3_imports_and_is_searchable(
        self,
        layered_import_page: LayeredImportPage,
        tmp_path: Path,
    ):
        """覆盖前后端一致性：校验通过后点击导入，列表可按表英文名查到新增实体。"""
        _require_uat_or_pre()
        run_id = import_run_id("m03_same_table_import")
        table_english_name = f"auto_same_table_import_{run_id[-8:]}"
        layer_paths = _layer_paths(run_id, "diff_l3")

        layered_import_page.open_m03_entity_import_dialog()
        build_upload_validate(
            layered_import_page,
            tmp_path,
            run_id,
            lambda headers: m03_same_system_table_rows(headers, table_english_name, layer_paths),
        )
        _assert_no_old_duplicate_error(layered_import_page.get_dialog_text())
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.click_confirm_import()
        _finalize_import(layered_import_page, reopen_data_resource_mgmt=True)
        layered_import_page.search_and_verify_entity(
            table_english_name,
            require_result=settings.ENV != "pre",
        )

    def test_m03_same_system_same_table_validation_does_not_write_before_import(
        self,
        layered_import_page: LayeredImportPage,
        tmp_path: Path,
    ):
        """校验通过但未点击导入前，不提前落库。"""
        _require_uat_or_pre()
        run_id = import_run_id("m03_same_table_nowrite")
        table_english_name = f"auto_same_table_nowrite_{run_id[-8:]}"
        layer_paths = _layer_paths(run_id, "diff_l2")

        layered_import_page.open_m03_entity_import_dialog()
        build_upload_validate(
            layered_import_page,
            tmp_path,
            run_id,
            lambda headers: m03_same_system_table_rows(headers, table_english_name, layer_paths),
        )
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.close_import_dialog()
        layered_import_page.should_show_no_search_results(table_english_name)

    def test_m03_full_business_tuple_duplicate_still_requires_duplicate_handling(
        self,
        layered_import_page: LayeredImportPage,
        tmp_path: Path,
    ):
        """完整业务定位元组相同仍应识别为重复，避免本次放开规则过宽。"""
        _require_uat_or_pre()
        run_id = import_run_id("m03_full_tuple_dup")
        table_english_name = f"auto_full_tuple_dup_{run_id[-8:]}"
        layer_paths = _layer_paths(run_id, "diff_l3")[:1]

        layered_import_page.open_m03_entity_import_dialog()
        template_file = layered_import_page.download_template(tmp_path)
        headers = read_first_sheet_headers(template_file)
        duplicate_rows = m03_same_system_table_rows(headers, table_english_name, [layer_paths[0], layer_paths[0]])
        import_file = create_workbook_from_headers(tmp_path, f"{run_id}.xlsx", headers, duplicate_rows)
        layered_import_page.upload_file(import_file)
        layered_import_page.click_validate_table()
        dialog_text = layered_import_page.get_dialog_text()
        assert any(text in dialog_text for text in ["重复", "跳过", "覆盖"]), f"完整元组重复未展示重复处理: {dialog_text[:500]}"
        layered_import_page.close_import_dialog()


@pytest.mark.dataresources
@pytest.mark.layered_import
@pytest.mark.regression
@pytest.mark.write
class TestM04SameSystemTableLocator20260907:
    """M04 在同系统同表英文名场景下按完整业务层级定位目标实体。"""

    def test_m04_same_system_same_table_uses_full_business_tuple_for_locator(
        self,
        layered_import_page: LayeredImportPage,
        tmp_path: Path,
    ):
        """同表英文名存在多实体时，M04 合法完整元组通过，未挂接实体的元组失败。"""
        _require_uat_or_pre()
        run_id = import_run_id("m04_same_table_tuple")
        table_english_name = f"auto_same_table_attr_{run_id[-8:]}"
        imported_paths = _layer_paths(run_id, "diff_l3")
        extra_path = _m03_context() | {"l1": "中建云测试专用L1_03", "l2": "中建云测试专用L2_03", "l3": "中建云测试专用L3_03"}

        layered_import_page.open_m03_entity_import_dialog()
        build_upload_validate(
            layered_import_page,
            tmp_path,
            f"{run_id}_m03",
            lambda headers: m03_same_system_table_rows(headers, table_english_name, imported_paths),
        )
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.click_confirm_import()
        _finalize_import(layered_import_page)

        layered_import_page.open_m04_attribute_import_dialog()
        m04_headers = m04_attribute_template_headers()
        import_file_ok = create_workbook_from_headers(
            tmp_path,
            f"{run_id}_m04_ok.xlsx",
            m04_headers,
            m04_same_system_table_attribute_row(
                m04_headers,
                table_english_name,
                f"auto_field_ok_{run_id[-8:]}",
                imported_paths[0],
            ),
        )
        layered_import_page.upload_file(import_file_ok)
        layered_import_page.click_validate_table()
        layered_import_page.should_allow_import_after_validation()
        layered_import_page.close_import_dialog()

        layered_import_page.open_m04_attribute_import_dialog()
        import_file_bad = create_workbook_from_headers(
            tmp_path,
            f"{run_id}_m04_bad.xlsx",
            m04_headers,
            m04_same_system_table_attribute_row(
                m04_headers,
                table_english_name,
                f"auto_field_bad_{run_id[-8:]}",
                extra_path,
            ),
        )
        layered_import_page.upload_file(import_file_bad)
        layered_import_page.click_validate_table()
        layered_import_page.should_show_import_errors(["校验失败", "错误", "行"])
        layered_import_page.should_not_allow_import()
        layered_import_page.close_import_dialog()
