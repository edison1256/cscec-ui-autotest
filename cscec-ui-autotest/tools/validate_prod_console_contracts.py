#!/usr/bin/env python3
"""Validate production console contracts against collected pytest nodes."""

from __future__ import annotations

import ast
from collections import Counter
import os
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.execution_contract import (  # noqa: E402
    CaseClassification,
    CaseContract,
    CaseContractRegistry,
    EntryType,
)


EXPECTED_TOTAL = 44
EXPECTED_COUNTS = {
    CaseClassification.MANDATORY: 7,
    CaseClassification.CONDITIONAL: 35,
    CaseClassification.PROBE: 2,
    CaseClassification.CONTROLLED_WRITE: 0,
}


def collect_console_nodes(marker: str | None = None) -> list[str]:
    """Collect console pytest nodes without opening a browser."""
    command = [
        _project_python(),
        "-m",
        "pytest",
        "tests/console",
        "--collect-only",
        "-q",
        "-o",
        "addopts=",
    ]
    if marker:
        command.extend(["-m", marker])
    environment = os.environ.copy()
    environment.setdefault("ENV", "uat")
    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        env=environment,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "pytest collection failed:\n" + (result.stdout + result.stderr)[-4000:]
        )
    return [
        line.strip().replace("\\", "/")
        for line in result.stdout.splitlines()
        if line.strip().startswith("tests/") and "::" in line
    ]


def validate_contracts(
    registry: CaseContractRegistry,
    collected_nodes: list[str],
    mandatory_nodes: list[str],
) -> list[str]:
    """Return all contract errors without stopping at the first defect."""
    errors: list[str] = []
    contracts = registry.contracts
    if len(contracts) != EXPECTED_TOTAL:
        errors.append(f"expected {EXPECTED_TOTAL} contracts, found {len(contracts)}")

    counts = Counter(contract.classification for contract in contracts)
    for classification, expected in EXPECTED_COUNTS.items():
        actual = counts[classification]
        if actual != expected:
            errors.append(
                f"expected {expected} {classification.value} contracts, found {actual}"
            )

    for contract in contracts:
        errors.extend(_validate_contract_fields(contract))
        matches = [node for node in collected_nodes if contract.matches_node(node)]
        if len(matches) != 1:
            errors.append(
                f"{contract.case_id}: expected exactly one collected node, found {len(matches)}"
            )
        errors.extend(_validate_test_source(contract))

    matched_node_ids = []
    for node in collected_nodes:
        matches = [contract for contract in contracts if contract.matches_node(node)]
        if len(matches) == 1:
            matched_node_ids.append(node)
        elif len(matches) > 1:
            ids = ", ".join(contract.case_id for contract in matches)
            errors.append(f"collected node matches multiple contracts: {node}: {ids}")
    if len(matched_node_ids) != EXPECTED_TOTAL:
        errors.append(
            f"contracts matched {len(matched_node_ids)} collected nodes, expected {EXPECTED_TOTAL}"
        )

    mandatory_contracts = [
        contract
        for contract in contracts
        if contract.classification is CaseClassification.MANDATORY
    ]
    for contract in mandatory_contracts:
        matches = [node for node in mandatory_nodes if contract.matches_node(node)]
        if len(matches) != 1:
            errors.append(
                f"{contract.case_id}: prod_mandatory marker selected {len(matches)} nodes"
            )
    if len(mandatory_nodes) != EXPECTED_COUNTS[CaseClassification.MANDATORY]:
        errors.append(
            f"prod_mandatory collects {len(mandatory_nodes)} nodes, expected "
            f"{EXPECTED_COUNTS[CaseClassification.MANDATORY]}"
        )

    return errors


def _validate_contract_fields(contract: CaseContract) -> list[str]:
    errors: list[str] = []
    if contract.max_depth not in {f"L{index}" for index in range(7)}:
        errors.append(f"{contract.case_id}: invalid max_depth {contract.max_depth}")
    if not contract.expected_state:
        errors.append(f"{contract.case_id}: expected_state is required")
    if not contract.owner_note.strip():
        errors.append(f"{contract.case_id}: owner_note is required")
    if contract.classification is CaseClassification.CONDITIONAL and not contract.prerequisites:
        errors.append(f"{contract.case_id}: Conditional prerequisites are required")
    if contract.classification is CaseClassification.MANDATORY:
        if contract.entry_type is EntryType.DIRECT:
            errors.append(f"{contract.case_id}: Mandatory cannot use DIRECT entry")
        if not contract.critical_api_patterns and not contract.critical_api_rationale.strip():
            errors.append(
                f"{contract.case_id}: Mandatory requires critical_api_patterns or a rationale"
            )
    for index, rule in enumerate(contract.ignore_rules, 1):
        missing = {
            "category",
            "detail_pattern",
            "reason",
            "expires_on",
        } - set(rule)
        if missing:
            errors.append(
                f"{contract.case_id}: ignore rule #{index} missing {sorted(missing)}"
            )
    return errors


def _validate_test_source(contract: CaseContract) -> list[str]:
    if contract.classification is not CaseClassification.MANDATORY:
        return []

    parts = contract.test_path.split("::")
    file_path = PROJECT_ROOT / parts[0]
    if not file_path.exists() or len(parts) != 3:
        return [f"{contract.case_id}: invalid test_path {contract.test_path}"]

    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    class_node = next(
        (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == parts[1]),
        None,
    )
    if class_node is None:
        return [f"{contract.case_id}: test class not found: {parts[1]}"]
    function_node = next(
        (
            node
            for node in class_node.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == parts[2]
        ),
        None,
    )
    if function_node is None:
        return [f"{contract.case_id}: test function not found: {parts[2]}"]

    errors: list[str] = []
    decorators = [ast.unparse(node) for node in class_node.decorator_list]
    decorators.extend(ast.unparse(node) for node in function_node.decorator_list)
    if not any("pytest.mark.prod_mandatory" in value for value in decorators):
        errors.append(f"{contract.case_id}: prod_mandatory marker is missing")

    source_calls = [ast.unparse(node.func) for node in ast.walk(function_node) if isinstance(node, ast.Call)]
    prohibited = {
        "pytest.skip": "pytest.skip",
        "pytest.xfail": "pytest.xfail",
        "time.sleep": "time.sleep",
    }
    for call_name, label in prohibited.items():
        if call_name in source_calls:
            errors.append(f"{contract.case_id}: Mandatory uses prohibited {label}")
    if any(name.endswith(".wait_for_timeout") for name in source_calls):
        errors.append(f"{contract.case_id}: Mandatory uses prohibited wait_for_timeout")
    return errors


def _project_python() -> str:
    candidate = PROJECT_ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    return str(candidate) if candidate.exists() else sys.executable


def main() -> int:
    try:
        registry = CaseContractRegistry.load()
        collected_nodes = collect_console_nodes()
        mandatory_nodes = collect_console_nodes("prod_mandatory")
        errors = validate_contracts(registry, collected_nodes, mandatory_nodes)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    counts = Counter(contract.classification.value for contract in registry.contracts)
    print("Production console contracts valid")
    print(f"Cases: {len(registry.contracts)}")
    print(
        "Classifications: "
        + ", ".join(f"{name}={count}" for name, count in sorted(counts.items()))
    )
    print(f"prod_mandatory collected: {len(mandatory_nodes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
