"""Machine-readable execution contracts for production console cases."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Mapping

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONTRACT_PATH = (
    PROJECT_ROOT / "test_assets" / "registry" / "prod_console_case_contracts.yaml"
)


class CaseClassification(StrEnum):
    """Release responsibility assigned to a production case."""

    MANDATORY = "mandatory"
    CONDITIONAL = "conditional"
    PROBE = "probe"
    CONTROLLED_WRITE = "controlled_write"


class EntryType(StrEnum):
    """How a test reaches its target surface."""

    UI = "UI"
    DIRECT = "DIRECT"
    HYBRID = "HYBRID"


@dataclass(frozen=True)
class CaseContract:
    """One expanded production console case contract."""

    case_id: str
    test_path: str
    parameter_id: str | None
    classification: CaseClassification
    entry_type: EntryType
    max_depth: str
    prerequisites: tuple[Mapping[str, Any], ...]
    expected_state: tuple[str, ...]
    critical_api_patterns: tuple[str, ...]
    critical_api_rationale: str
    ignore_rules: tuple[Mapping[str, Any], ...]
    owner_note: str

    def matches_node(self, node_id: str) -> bool:
        """Return whether a collected pytest node belongs to this contract."""
        normalized = node_id.replace("\\", "/")
        expected = self.test_path.replace("\\", "/")
        if not normalized.startswith(expected):
            return False
        return self.parameter_id is None or self.parameter_id in normalized


@dataclass(frozen=True)
class PrerequisiteResult:
    """Result of checking one case prerequisite before UI actions start."""

    satisfied: bool
    reason: str
    expected: str = ""
    actual: str = ""

    def require_for(self, contract: CaseContract) -> None:
        """Fail Mandatory cases and flag Conditional cases distinctly."""
        if self.satisfied:
            return
        detail = (
            f"{contract.case_id} 前置条件不满足: {self.reason}; "
            f"expected={self.expected!r}, actual={self.actual!r}"
        )
        if contract.classification is CaseClassification.CONDITIONAL:
            raise ConditionalNotApplicable(detail)
        raise AssertionError(detail)


class ConditionalNotApplicable(RuntimeError):
    """A declared Conditional prerequisite was false before UI work began."""


class CaseContractRegistry:
    """Load and query the production console case contract registry."""

    def __init__(self, contracts: tuple[CaseContract, ...]) -> None:
        self.contracts = contracts
        self._by_id = {contract.case_id: contract for contract in contracts}

    @classmethod
    def load(cls, path: Path = DEFAULT_CONTRACT_PATH) -> "CaseContractRegistry":
        """Load contracts from YAML and validate required value types."""
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        raw_cases = payload.get("cases")
        if not isinstance(raw_cases, list):
            raise ValueError(f"Contract registry must contain a cases list: {path}")

        contracts: list[CaseContract] = []
        for index, raw in enumerate(raw_cases, 1):
            if not isinstance(raw, dict):
                raise ValueError(f"Contract #{index} must be an object")
            try:
                contract = CaseContract(
                    case_id=str(raw["case_id"]),
                    test_path=str(raw["test_path"]),
                    parameter_id=(
                        str(raw["parameter_id"])
                        if raw.get("parameter_id") is not None
                        else None
                    ),
                    classification=CaseClassification(raw["classification"]),
                    entry_type=EntryType(raw["entry_type"]),
                    max_depth=str(raw["max_depth"]),
                    prerequisites=tuple(raw.get("prerequisites") or ()),
                    expected_state=tuple(raw.get("expected_state") or ()),
                    critical_api_patterns=tuple(
                        raw.get("critical_api_patterns") or ()
                    ),
                    critical_api_rationale=str(
                        raw.get("critical_api_rationale") or ""
                    ),
                    ignore_rules=tuple(raw.get("ignore_rules") or ()),
                    owner_note=str(raw.get("owner_note") or ""),
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"Invalid contract #{index}: {raw!r}") from exc
            contracts.append(contract)

        case_ids = [contract.case_id for contract in contracts]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("Contract registry contains duplicate case_id values")
        return cls(tuple(contracts))

    def require(self, case_id: str) -> CaseContract:
        """Return one contract or fail with a stable diagnostic."""
        try:
            return self._by_id[case_id]
        except KeyError as exc:
            raise KeyError(f"Production console contract not found: {case_id}") from exc

    def find_for_node(self, node_id: str) -> CaseContract | None:
        """Return the unique contract matching a collected pytest node."""
        matches = [contract for contract in self.contracts if contract.matches_node(node_id)]
        if len(matches) > 1:
            ids = ", ".join(contract.case_id for contract in matches)
            raise ValueError(f"Pytest node matches multiple contracts: {node_id}: {ids}")
        return matches[0] if matches else None
