"""Tests for the production console machine-readable contract registry."""

from __future__ import annotations

from collections import Counter

from core.execution_contract import CaseClassification, CaseContractRegistry
from tools.validate_prod_console_contracts import (
    collect_console_nodes,
    validate_contracts,
)


def test_contract_registry_has_reviewed_classification_counts() -> None:
    registry = CaseContractRegistry.load()
    counts = Counter(contract.classification for contract in registry.contracts)

    assert len(registry.contracts) == 107
    assert counts == {
        CaseClassification.MANDATORY: 44,
        CaseClassification.CONDITIONAL: 63,
    }


def test_contracts_match_collection_and_mandatory_markers() -> None:
    registry = CaseContractRegistry.load()

    errors = validate_contracts(
        registry,
        collect_console_nodes(),
        collect_console_nodes("prod_mandatory"),
        collect_console_nodes("prod_conditional"),
    )

    assert errors == []
