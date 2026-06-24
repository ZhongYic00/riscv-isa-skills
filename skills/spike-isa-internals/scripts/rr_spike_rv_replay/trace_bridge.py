"""Trace parsing and target resolution for Spike replay."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TraceRecord:
    index: int
    pc: str | None = None
    binary: str | None = None
    text: str | None = None
    hart_id: int | None = None


def _coerce_record(item: dict[str, Any]) -> TraceRecord:
    if "index" not in item:
        raise ValueError("trace record missing required field: index")
    return TraceRecord(
        index=int(item["index"]),
        pc=item.get("pc"),
        binary=item.get("binary"),
        text=item.get("text"),
        hart_id=int(item["hart_id"]) if item.get("hart_id") is not None else None,
    )


def parse_trace_file(trace_path: str | Path) -> list[TraceRecord]:
    payload = json.loads(Path(trace_path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        raw_records = payload.get("instructions")
    elif isinstance(payload, list):
        raw_records = payload
    else:
        raise ValueError("trace payload must be an object or list")
    if not isinstance(raw_records, list):
        raise ValueError("trace payload must contain instruction list")
    return [_coerce_record(item) for item in raw_records]


def _apply_stop_policy(matches: list[TraceRecord], stop_policy: str, nth: int) -> TraceRecord | None:
    if not matches:
        return None
    if stop_policy == "nth-hit":
        index = nth - 1
        if 0 <= index < len(matches):
            return matches[index]
        return None
    return matches[0]


def _record_matches_pattern(record: TraceRecord, pattern: str) -> bool:
    for field in (record.text, record.binary):
        if field and re.search(pattern, field):
            return True
    return False


def _record_matches_substring(record: TraceRecord, needle: str) -> bool:
    normalized = needle.lower()
    for field in (record.text, record.binary):
        if field and normalized in field.lower():
            return True
    return False


def _nearby_samples(records: list[TraceRecord]) -> str:
    if not records:
        return "none"
    if len(records) <= 4:
        return ", ".join(str(item.index) for item in records)
    picks = records[:2] + records[-2:]
    return ", ".join(str(item.index) for item in picks)


def resolve_target_from_trace(
    records: list[TraceRecord],
    *,
    target_insn_index: int | None = None,
    target_pc: str | None = None,
    rv_instr_pattern: str | None = None,
    rv_instr: str | None = None,
    stop_policy: str = "first-hit",
    nth: int = 1,
    hart_id: int | None = None,
) -> tuple[TraceRecord | None, str, list[str]]:
    scoped = [record for record in records if hart_id is None or record.hart_id == hart_id]

    if target_insn_index is not None:
        selected = _apply_stop_policy([record for record in scoped if record.index == target_insn_index], stop_policy, nth)
    elif target_pc:
        selected = _apply_stop_policy(
            [record for record in scoped if record.pc and record.pc.lower() == target_pc.lower()],
            stop_policy,
            nth,
        )
    elif rv_instr_pattern:
        selected = _apply_stop_policy([record for record in scoped if _record_matches_pattern(record, rv_instr_pattern)], stop_policy, nth)
    elif rv_instr:
        selected = _apply_stop_policy([record for record in scoped if _record_matches_substring(record, rv_instr)], stop_policy, nth)
    else:
        selected = _apply_stop_policy(scoped, stop_policy, nth)

    if selected is not None:
        return selected, "target-match", []

    hints = [
        f"Try a nearby target_pc or target_insn_index. Nearby trace indexes: {_nearby_samples(scoped or records)}.",
        "If this target is late in execution, rerun with broader selectors or a lower nth value.",
    ]
    return None, "no-trace-match", hints
