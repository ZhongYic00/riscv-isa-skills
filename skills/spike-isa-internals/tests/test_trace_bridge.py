import json

from rr_spike_rv_replay.trace_bridge import TraceRecord, parse_trace_file, resolve_target_from_trace


def test_parse_trace_file_accepts_wrapped_instructions_object(tmp_path) -> None:
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        json.dumps({"instructions": [{"index": 1, "pc": "0x100", "text": "addi x1, x0, 1"}]}),
        encoding="utf-8",
    )

    records = parse_trace_file(trace_path)

    assert records == [TraceRecord(index=1, pc="0x100", binary=None, text="addi x1, x0, 1", hart_id=None)]


def test_parse_trace_file_accepts_top_level_instruction_list(tmp_path) -> None:
    trace_path = tmp_path / "trace_list.json"
    trace_path.write_text(
        json.dumps([
            {"index": 2, "pc": "0x104", "binary": "0x00a00513", "text": "addi a0, zero, 10", "hart_id": 1}
        ]),
        encoding="utf-8",
    )

    records = parse_trace_file(trace_path)

    assert records[0].index == 2
    assert records[0].pc == "0x104"
    assert records[0].binary == "0x00a00513"
    assert records[0].hart_id == 1


def test_resolve_target_from_trace_uses_nth_hit_and_hart_id_filter() -> None:
    records = [
        TraceRecord(index=1, pc="0x100", binary="0x111", text="addi x1, x0, 1", hart_id=0),
        TraceRecord(index=2, pc="0x100", binary="0x222", text="addi x2, x0, 2", hart_id=1),
        TraceRecord(index=3, pc="0x100", binary="0x333", text="addi x3, x0, 3", hart_id=1),
    ]

    selected, status, hints = resolve_target_from_trace(
        records,
        target_pc="0x100",
        stop_policy="nth-hit",
        nth=2,
        hart_id=1,
    )

    assert status == "target-match"
    assert selected is not None
    assert selected.index == 3
    assert hints == []


def test_resolve_target_from_trace_reports_nearby_records_and_rerun_hints_when_no_match() -> None:
    records = [
        TraceRecord(index=10, pc="0x100", binary="0x111", text="addi x1, x0, 1", hart_id=0),
        TraceRecord(index=11, pc="0x104", binary="0x222", text="addi x2, x0, 2", hart_id=0),
        TraceRecord(index=12, pc="0x108", binary="0x333", text="addi x3, x0, 3", hart_id=0),
    ]

    selected, status, hints = resolve_target_from_trace(
        records,
        target_pc="0x999",
        stop_policy="first-hit",
        nth=1,
    )

    assert selected is None
    assert status == "no-trace-match"
    assert hints
    assert "Try a nearby target_pc" in hints[0]


def test_resolve_target_from_trace_uses_selector_priority() -> None:
    records = [
        TraceRecord(index=20, pc="0x200", binary="0xaaaa", text="nop", hart_id=0),
        TraceRecord(index=21, pc="0x300", binary="0xbbbb", text="ecall", hart_id=0),
    ]

    selected, status, _hints = resolve_target_from_trace(
        records,
        target_insn_index=20,
        target_pc="0x300",
        rv_instr_pattern="ecall",
        rv_instr="bbbb",
        stop_policy="first-hit",
        nth=1,
    )

    assert status == "target-match"
    assert selected is not None
    assert selected.index == 20
