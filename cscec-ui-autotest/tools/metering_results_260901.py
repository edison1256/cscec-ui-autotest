"""Current-run, phase-aware results for metering regression."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

CASE_PATTERN = re.compile(r"test_([mf])(\d+)(?:_(\d+)_(\d+)[a-z]?)?__", re.I)
CLASS_PATTERN = re.compile(
    r"ENV_MISMATCH|ENTRY_MISSING|ROLE_REQUIRED|DATA_REQUIRED|"
    r"PENDING_IMPLEMENTATION|OUT_OF_SCOPE|NOT_AUTOMATABLE|ENV_LIMITED|CONTRACT_DIFFERENCE|WRITE_BLOCKED"
)
SUITE_PATH = "tests/metering_subscription_260901/"


def is_metering_node(nodeid: str) -> bool:
    path = nodeid.split("::", 1)[0].replace("\\", "/").lower()
    return "/" + SUITE_PATH in "/" + path


def case_id_from_nodeid(nodeid: str) -> str | None:
    if not is_metering_node(nodeid):
        return None
    match = CASE_PATTERN.search(nodeid.rsplit("::", 1)[-1])
    if not match:
        return None
    letter, module, section, index = match.groups()
    return f"{letter.upper()}{module}" + (f".{section}.{index}" if section else "")


class ResultRecorder:
    """Aggregate all phases/variants; never load another run's outcomes."""

    def __init__(self, path: Path, env: str) -> None:
        self.path = path
        self.env = env
        self.run_id = uuid4().hex
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.nodes: dict[str, dict] = {}
        self.results: dict[str, dict] = {}
        self.case_nodes: dict[str, set[str]] = {}

    def consume(self, report) -> None:
        if not is_metering_node(report.nodeid):
            return
        properties = dict(getattr(report, "user_properties", []))
        legacy_id = case_id_from_nodeid(report.nodeid)
        case_ids = json.loads(properties["metering_case_ids"]) if "metering_case_ids" in properties else [legacy_id] if legacy_id else []
        if not case_ids:
            return
        assert all(re.fullmatch(r"[MF]\d+(?:\.\d+)*", cid) for cid in case_ids)
        entry = self.nodes.setdefault(
            report.nodeid,
            {"nodeid": report.nodeid, "title": report.nodeid.rsplit("::", 1)[-1],
             "status": "not_run", "phases": {}},
        )
        entry["title"] = dict(getattr(report, "user_properties", [])).get(
            "metering_title", entry["title"]
        )
        phase = {"status": report.outcome}
        reason = str(report.longrepr) if report.longrepr else ""
        if report.failed:
            phase["error"] = reason if len(reason) <= 2400 else reason[:600] + "\n...[truncated]...\n" + reason[-1800:]
        elif report.skipped:
            phase["skip_reason"] = reason[-800:]
        crash = getattr(report.longrepr, "reprcrash", None)
        match = CLASS_PATTERN.search(getattr(crash, "message", reason))
        if match:
            phase["classification"] = match.group()
        entry["phases"][report.when] = phase
        phases = entry["phases"]
        decisive = next((p for p in phases.values() if p["status"] == "failed"), None)
        decisive = decisive or next((p for p in phases.values() if p["status"] == "skipped"), None)
        decisive = decisive or phases.get("call", {"status": "not_run"})
        for key in ("status", "error", "skip_reason", "classification"):
            entry.pop(key, None)
        entry.update(decisive)
        priority = {"failed": 4, "skipped": 3, "not_run": 2, "passed": 1}
        titles = json.loads(properties.get("metering_case_titles", "{}"))
        scope_notes = json.loads(properties.get("metering_scope_notes", "{}"))
        if "metering_artifacts" in properties:
            entry["artifacts"] = properties["metering_artifacts"]
        for property_name in ("metering_traces", "metering_trace_errors"):
            if property_name in properties:
                entry[property_name] = json.loads(properties[property_name])
        for case_id in case_ids:
            self.case_nodes.setdefault(case_id, set()).add(report.nodeid)
            variants = [self.nodes[node] for node in sorted(self.case_nodes[case_id])]
            worst = max(variants, key=lambda n: priority[n["status"]])
            self.results[case_id] = {**worst, "title": titles.get(case_id, worst["title"]), "variants": variants}
            if case_id in scope_notes:
                self.results[case_id]["scope_note"] = scope_notes[case_id]

    def flush(self, exitstatus: int) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": 2, "run_id": self.run_id, "env": self.env,
                   "started_at": self.started_at,
                   "generated_at": datetime.now(timezone.utc).isoformat(),
                   "exitstatus": int(exitstatus), "results": self.results}
        for path in (self.path, self.path.parent / "runs" / self.run_id / "results.json"):
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_name(f".{path.name}.{self.run_id}.tmp")
            try:
                temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
