"""ISA-level event extraction around a target instruction index."""

from __future__ import annotations

from rr_spike_rv_replay.trace_bridge import TraceRecord


def classify_isa_event(text: str | None) -> str | None:
    if not text:
        return None
    lowered = text.lower().strip()
    if lowered.startswith("csrrw") or lowered.startswith("csrrs") or lowered.startswith("csrrc"):
        return "csr-read-write"
    if lowered.startswith("csrr") or lowered.startswith("frcsr"):
        return "csr-read"
    if lowered.startswith("csrw") or lowered.startswith("csrs") or lowered.startswith("csrc") or lowered.startswith("fscsr"):
        return "csr-write"
    if "ecall" in lowered or "ebreak" in lowered or lowered.startswith("mret") or lowered.startswith("sret"):
        return "trap"
    return None


def extract_isa_events(
    records: list[TraceRecord],
    *,
    target_index: int,
    before: int,
    after: int,
    hart_id: int | None = None,
) -> list[dict[str, object]]:
    start = target_index - before
    end = target_index + after
    out: list[dict[str, object]] = []
    for record in records:
        if hart_id is not None and record.hart_id != hart_id:
            continue
        if not (start <= record.index <= end):
            continue
        event_type = classify_isa_event(record.text)
        if event_type is None:
            continue
        out.append(
            {
                "index": record.index,
                "pc": record.pc,
                "hart_id": record.hart_id,
                "text": record.text,
                "event_type": event_type,
                "is_target": record.index == target_index,
            }
        )
    return out
